#!/usr/bin/env python3
"""
pauta_cidade.py — gera, sem LLM, os dados da "pauta de conversas" (2º turno)
de um município a partir dos dados públicos do app "Onde dá pra conversar"
(ondedapraconversar.com.br), e devolve um JSON.

Uso:
    python3 pauta_cidade.py "Cachoeira do Sul, RS"                 # busca online
    python3 pauta_cidade.py "Cachoeira do Sul, RS" -o cachoeira.json
    python3 pauta_cidade.py "Bagé, RS" --celulas celulas-bage.json --marcas marcas-bage.json   # offline
    python3 pauta_cidade.py "Uruguaiana/RS" --salvar-dados          # grava os 4 arquivos em dados/app/

Só usa a biblioteca padrão do Python (3.9+). Logs vão para stderr; o JSON vai
para stdout (ou para o arquivo de -o).

As fichas do app (frases, roteiros, as 6 pontes de cada candidato) vêm
embutidas no script. Se existir --dados/fichas-conversas.json, ele tem
prioridade (útil quando o app atualizar as fichas). O mesmo vale para
--dados/propostas-temas.json (títulos e nº de propostas dos 12 temas).
"""
import argparse
import collections
import datetime
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.ondedapraconversar.com.br"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pauta-cidade/1.1"}

# Tamanho do quadriculado dos arquivos de células, em graus. O valor vem de
# /dados/indice.json -> "celula" (o app já usou 0.25 e hoje usa 0.1); este é
# só o padrão se o índice não vier.
# Tile = f"{floor(lat*k)}_{floor(lon*k)}", k = round(1/celula) (ex.: -301_-530 com 0.1).
TAMANHO_TILE_PADRAO = 0.1

LULA, FLAVIO = "13", "22"
# candidatos com ficha de "ponte" -> chave da ficha
PONTE = {"55": "caiado", "70": "cury", "14": "renan", "30": "zema"}
NOMES_PADRAO = {
    "13": "Lula", "22": "Flávio Bolsonaro", "14": "Renan Santos",
    "70": "Augusto Cury", "55": "Ronaldo Caiado", "30": "Romeu Zema",
    "80": "Samara", "27": "Clariana Barao", "16": "Hertz Dias",
    "21": "Edmilson Costa", "35": "Veterinário Wilson Grassi",
    "29": "Rui Costa Pimenta", "28": "número 28",
}
NOME_CURTO = {"55": "Caiado", "70": "Cury", "14": "Renan", "30": "Zema"}

# ---- limiares da leitura estratégica (ajuste aqui) -------------------------
LIMIAR_EMPATE_PP = 6.0        # diferença ≤ 6pp de válidos -> cidade de empate
LIMIAR_COMPETITIVO_PP = 10.0  # bairro com Flávio à frente por ≤ 10pp -> conversável
LIMIAR_ABSTENCAO_ALTA = 30.0  # bairro com abstenção ≥ 30% do eleitorado
TOP_ONDE = 5                  # quantos bairros listar no "onde" de cada pauta

# ---- 12 temas das Propostas -------------------------------------------------
TITULOS_TEMAS = {
    "saude": "Saúde",
    "trabalho-e-renda": "Trabalho e renda",
    "comida-e-custo-de-vida": "Comida e custo de vida",
    "educacao": "Educação",
    "seguranca": "Segurança",
    "moradia-e-bairro": "Moradia e bairro",
    "aposentados-e-idosos": "Aposentados e idosos",
    "mulheres": "Mulheres",
    "juventude": "Juventude",
    "pequenos-negocios": "Pequenos negócios",
    "campo": "Campo",
    "meio-ambiente": "Meio ambiente",
}

# Palavras-chave (sem acento, minúsculas) que ligam o `tema` de uma ponte aos
# 12 temas das Propostas. Uma ponte pode cair em mais de um tema.
PALAVRAS_TEMA = [
    ("saude", ["sus", "saude", "prontuario", "consulta", "medic", "hospital", "fila"]),
    ("educacao", ["escola", "aluno", "ensino", "alfabet", "lendo", "estudo"]),
    ("juventude", ["ensino tecnico", "jovem", "juventude"]),
    ("seguranca", ["seguranca", "crime", "faccao", "faccoes", "fronteira", "policia", "agressor"]),
    ("mulheres", ["mulher", "lilas", "agressor"]),
    ("trabalho-e-renda", ["renda", "trabalho", "cooperativa", "salario", "industria", "terras raras", "bolsa"]),
    ("campo", ["rural", "safra", "campo", "agro"]),
    ("moradia-e-bairro", ["agua", "esgoto", "saneamento", "moradia"]),
    ("pequenos-negocios", ["pequeno negocio", "pequenos negocios", "empreend"]),
    ("comida-e-custo-de-vida", ["comida", "preco", "custo de vida", "alimento"]),
    ("aposentados-e-idosos", ["aposentad", "idoso"]),
    ("meio-ambiente", ["ambiente", "clima", "desmatamento"]),
]

# Temas para as pautas que não têm ponte (voto/abstenção/converter/segurar).
# Os de abstenção/branco/nulo seguem o roteiro das fichas: "o preço da comida,
# a fila do posto, a escola das crianças". Ajuste aqui se a §6 das pautas
# publicadas usar outra tabela.
TEMAS_POR_PAUTA = {
    "abstencao": ["comida-e-custo-de-vida", "saude", "educacao", "aposentados-e-idosos"],
    "branco": ["comida-e-custo-de-vida", "saude", "educacao", "trabalho-e-renda"],
    "nulo": ["comida-e-custo-de-vida", "trabalho-e-renda", "saude", "seguranca"],
    "demais": ["trabalho-e-renda", "comida-e-custo-de-vida", "meio-ambiente", "mulheres"],
    "converter-flavio": ["seguranca", "saude", "pequenos-negocios", "campo"],
    "segurar-lula": ["aposentados-e-idosos", "saude", "comida-e-custo-de-vida", "moradia-e-bairro"],
}

# Cópia das fichas do app (fichas-conversas.json): frases, roteiros e os temas
# das 6 pontes de cada candidato. As citações literais dos programas ficam no
# arquivo completo; aqui vai só o necessário para a pauta.
FICHAS_EMBUTIDAS = r'''{
 "fichas": [
  {
   "tipo": "voto",
   "chave": "abstencao",
   "titulo": "Quem não foi votar",
   "frase": "Seu voto vale o mesmo que o de qualquer pessoa no Brasil. Mas só vale dentro da urna. O segundo turno se decide com você.",
   "apoio": "No dia 25 o país inteiro escolhe. Quem fica em casa deixa a escolha para os outros, logo cada voto é uma vitória para um Brasil melhor.",
   "explicacao": [
    "No segundo turno só contam os votos em Lula e Flávio. Quem não aparece fica fora da conta, e o resultado sai de quem foi.",
    "Faltou no primeiro turno? Pode votar normalmente no dia 25. A falta de agora dá pra justificar depois, pelo aplicativo e-Título."
   ],
   "roteiro": [
    "Pergunte como foi o domingo. Muita gente não votou por causa do trabalho, de um filho doente, da distância, da falta de tempo ou de esperança.",
    "Deixe a pessoa falar. Quem se sente ouvido escuta de volta.",
    "Conte que ela pode votar no dia 25, mesmo tendo faltado agora.",
    "Pergunte o que mais pesa no mês dela: o preço da comida, a fila do posto, a escola das crianças. Abra as Propostas e mostre o que o Lula vai fazer sobre isso.",
    "Na despedida, um convite simples: dia 25, vai lá. Sua voz faz falta. Se você não votar, a gente não pode reclamar com quem ganhou."
   ],
   "cuidado": "Nunca ofereça carona, comida, dinheiro ou favor em troca do voto. É crime, e a conversa perde todo o valor. E se a pessoa não quiser votar, não force."
  },
  {
   "tipo": "voto",
   "chave": "branco",
   "titulo": "Quem votou em branco",
   "frase": "Voto em branco é uma página que outra pessoa vai escrever por você.",
   "apoio": "No dia 25 são só dois nomes. Escolher um deles é o jeito de a sua opinião entrar na conta.",
   "explicacao": [
    "O voto em branco não vai para ninguém. Nem para quem está ganhando, nem para quem está perdendo. Ele simplesmente fica fora da conta.",
    "Quem decide o segundo turno é quem escolhe o Lula ou o Flávio. Cada voto em branco deixa a decisão do país na mão de menos gente."
   ],
   "roteiro": [
    "Pergunte, com curiosidade de verdade, por que a pessoa votou em branco.",
    "Quase sempre é cansaço. Diga que você entende: política cansa mesmo. Não ser ouvido cansa. Não ter esperança cansa. Mas votar branco não resolve nada. A escolha fica com os outros.",
    "Conte, do jeito mais simples que puder, que o branco não soma para ninguém e que a escolha fica com os outros.",
    "Pergunte o que ela quer ver mudar e mostre a proposta do Lula sobre isso, na página de Propostas.",
    "Feche com calma: dessa vez, escreve você."
   ],
   "cuidado": "Não diga que o branco vai para quem está ganhando. Não é verdade, e a pessoa passa a desconfiar de todo o resto."
  },
  {
   "tipo": "voto",
   "chave": "nulo",
   "titulo": "Quem anulou o voto",
   "frase": "Sua raiva tem motivo. No voto nulo, ela fica sem endereço.",
   "apoio": "No dia 25 dá pra transformar essa raiva em escolha.",
   "explicacao": [
    "O voto nulo não conta para ninguém e não cancela a eleição, por mais nulos que haja. Essa história de que muito nulo anula tudo é boato antigo.",
    "O segundo turno sai só dos votos no Lula e no Flávio. Quem anula sai da conta e deixa os outros decidirem."
   ],
   "roteiro": [
    "Pergunte o que fez a pessoa anular. Deixe ela desabafar até o fim.",
    "Não brigue com a raiva. Concorde com o que for justo.",
    "Conte que o nulo não derruba a eleição e não entra na conta.",
    "Mostre a proposta do Lula que responde ao que mais incomoda ela.",
    "Termine com uma pergunta: e se dessa vez a sua raiva tivesse endereço?"
   ],
   "cuidado": "Não chame o nulo de burrice nem de voto jogado fora. Quem se sente humilhado não volta a conversar."
  },
  {
   "tipo": "candidato",
   "chave": "cury",
   "titulo": "Quem votou no Augusto Cury",
   "nome": "Augusto Cury",
   "abertura": "O programa do Cury fala de escola, de saúde mental, de médico mais perto e de salário justo para as mulheres. Nisso tudo, ele e o Lula andam juntos.",
   "pontes": [
    {
     "tipo": "igual",
     "tema": "Escola em tempo integral",
     "emComum": "Os dois põem a escola em tempo integral no topo da lista da educação."
    },
    {
     "tipo": "igual",
     "tema": "Saúde mental",
     "emComum": "Os dois querem cuidar da saúde mental como política do país inteiro, passando pela escola e pelos jovens."
    },
    {
     "tipo": "igual",
     "tema": "Segurança com União, estados e municípios juntos",
     "emComum": "Para os dois, o crime organizado se enfrenta com União, estados e municípios do mesmo lado."
    },
    {
     "tipo": "igual",
     "tema": "Consulta a distância no SUS",
     "emComum": "Os dois querem consulta a distância dentro da saúde pública, para que morar longe deixe de ser motivo para ficar sem médico."
    },
    {
     "tipo": "igual",
     "tema": "Salário igual para mulheres",
     "emComum": "Os dois querem que a lei de salário igual entre mulheres e homens saia do papel, com fiscalização."
    },
    {
     "tipo": "aproximado",
     "tema": "Cooperativas que geram renda",
     "emComum": "Os dois apostam na cooperativa como jeito de gerar trabalho e renda. O Cury pensa em cooperativas grandes em vários setores; o Lula dá prioridade às cooperativas populares e à economia solidária."
    }
   ]
  },
  {
   "tipo": "candidato",
   "chave": "renan",
   "titulo": "Quem votou no Renan Santos",
   "nome": "Renan Santos",
   "abertura": "O Renan quer um SUS que funcione, o crime sem dinheiro e um Brasil que fabrique em vez de só exportar. O programa do Lula quer as mesmas coisas.",
   "pontes": [
    {
     "tipo": "igual",
     "tema": "Fila do SUS pela gravidade do caso",
     "emComum": "Os dois querem que a fila do SUS ande pela gravidade do caso: quem está pior é atendido antes."
    },
    {
     "tipo": "igual",
     "tema": "Prontuário único",
     "emComum": "Os dois querem que a história de saúde de cada pessoa ande com ela, do posto ao hospital."
    },
    {
     "tipo": "igual",
     "tema": "Fronteiras e dinheiro do crime",
     "emComum": "Os dois querem fechar a fronteira para o crime e cortar o dinheiro das facções."
    },
    {
     "tipo": "igual",
     "tema": "Terras raras transformadas aqui",
     "emComum": "Os dois querem que o Brasil pare de só vender terras raras em estado bruto e passe a transformar esse minério aqui dentro."
    },
    {
     "tipo": "aproximado",
     "tema": "Nordeste com indústria",
     "emComum": "Os dois veem o Nordeste como lugar de indústria, não de socorro. O Renan propõe zonas com regras especiais de imposto; o Lula quer atrair fábricas que usam o sol e o vento da região."
    },
    {
     "tipo": "aproximado",
     "tema": "Aluno aprendendo o básico",
     "emComum": "Os dois querem que o aluno da escola pública aprenda de verdade o básico. O Renan foca em português e matemática; o Lula propõe uma estratégia nacional para recuperar o que ficou para trás."
    }
   ]
  },
  {
   "tipo": "candidato",
   "chave": "caiado",
   "titulo": "Quem votou no Ronaldo Caiado",
   "nome": "Ronaldo Caiado",
   "abertura": "O Caiado fala de SUS com fila transparente, de segurança, de criança lendo cedo e de proteger quem planta. Nisso, o programa do Lula diz quase a mesma coisa.",
   "pontes": [
    {
     "tipo": "igual",
     "tema": "SUS com fila transparente",
     "emComum": "Os dois defendem o SUS com fila às claras e especialista mais rápido."
    },
    {
     "tipo": "igual",
     "tema": "Ministério da Segurança Pública",
     "emComum": "Os dois propõem criar o Ministério da Segurança Pública, trabalhando junto com os governadores."
    },
    {
     "tipo": "igual",
     "tema": "Água e esgoto para todo mundo",
     "emComum": "Os dois querem água tratada e esgoto na casa de todos os brasileiros."
    },
    {
     "tipo": "igual",
     "tema": "Criança lendo na idade certa",
     "emComum": "Os dois querem toda criança alfabetizada na idade certa, com o governo federal apoiando estados e prefeituras."
    },
    {
     "tipo": "igual",
     "tema": "Seguro rural mais forte",
     "emComum": "Os dois querem fortalecer o seguro rural, junto com o setor produtivo, para o produtor não perder tudo quando a safra quebra."
    },
    {
     "tipo": "igual",
     "tema": "Bolsa mantida, ligada a trabalho e estudo",
     "emComum": "Os dois mantêm a transferência de renda para quem precisa e querem ligar esse apoio a trabalho, estudo e saúde."
    }
   ]
  },
  {
   "tipo": "candidato",
   "chave": "zema",
   "titulo": "Quem votou no Romeu Zema",
   "nome": "Romeu Zema",
   "abertura": "O Zema quer prontuário único, fila da saúde organizada, as facções sem dinheiro e a mulher protegida. O programa do Lula tem tudo isso, com o governo federal puxando.",
   "pontes": [
    {
     "tipo": "igual",
     "tema": "Prontuário nacional",
     "emComum": "Os dois querem um prontuário nacional, com o governo federal puxando."
    },
    {
     "tipo": "aproximado",
     "tema": "Saneamento com estados e municípios",
     "emComum": "O caminho muda, o Zema aposta mais em concessões. O objetivo é o mesmo: saneamento para todo mundo, com União, estados e municípios juntos."
    },
    {
     "tipo": "igual",
     "tema": "Cortar o dinheiro das facções",
     "emComum": "Os dois querem sufocar o dinheiro das facções."
    },
    {
     "tipo": "igual",
     "tema": "Salas Lilás e agressor vigiado",
     "emComum": "Os dois prometem ampliar as Salas Lilás e vigiar de perto o agressor depois da denúncia."
    },
    {
     "tipo": "igual",
     "tema": "Inteligência artificial na fila da saúde",
     "emComum": "Os dois querem usar inteligência artificial para organizar a fila da saúde pública e mandar cada paciente para o atendimento certo."
    },
    {
     "tipo": "aproximado",
     "tema": "Mais ensino técnico",
     "emComum": "Os dois querem mais jovens fazendo curso técnico. O Zema aposta em parcerias com escolas privadas e o Sistema S; o Lula, em abrir mais institutos federais no interior e nas periferias."
    }
   ]
  }
 ],
 "roteiro_geral": [
  "Comece pelo que a pessoa gostou no candidato dela. Quem se sente respeitado baixa a guarda.",
  "Mostre um ponto em comum, com os dois trechos lado a lado. Cada um tem fonte e página, é só tocar.",
  "Não fale mal do candidato dela. Ela quer um país melhor, igual a você. A pergunta agora é quem leva isso adiante no dia 25.",
  "Se ela não decidir na hora, tudo bem. Agradeça e deixe a porta aberta. Voto se decide com tempo."
 ]
}'''

PROPOSTAS_EMBUTIDAS = r'''[
 {
  "chave": "saude",
  "titulo": "Saúde",
  "chamada": "Menos espera por especialista e exame, remédio de graça na farmácia e o SUS mais perto de casa, até no celular.",
  "propostas": [
   {
    "titulo": "Fila do SUS pela gravidade",
    "pagina": 38
   },
   {
    "titulo": "Mais consultas, exames e cirurgias",
    "pagina": 37
   },
   {
    "titulo": "Farmácia Popular segue de graça",
    "pagina": 36
   },
   {
    "titulo": "Exames na Farmácia Popular",
    "pagina": 36
   },
   {
    "titulo": "Consulta e exame no celular",
    "pagina": 35
   },
   {
    "titulo": "Médico perto de quem precisa",
    "pagina": 35
   },
   {
    "titulo": "Tratamento de câncer no SUS",
    "pagina": 38
   },
   {
    "titulo": "Dentista para todo mundo",
    "pagina": 36
   }
  ]
 },
 {
  "chave": "trabalho-e-renda",
  "titulo": "Emprego, salário e trabalho",
  "chamada": "Salário mínimo valorizado, fim da escala 6x1 e mais proteção para quem trabalha, inclusive por aplicativo.",
  "propostas": [
   {
    "titulo": "Fim da escala 6x1",
    "pagina": 75
   },
   {
    "titulo": "Salário mínimo com aumento real",
    "pagina": 74
   },
   {
    "titulo": "Vaga e curso no mesmo lugar",
    "pagina": 74
   },
   {
    "titulo": "Mais qualificação profissional",
    "pagina": 74
   },
   {
    "titulo": "Aposentadoria para quem é de aplicativo",
    "pagina": 77
   },
   {
    "titulo": "Contra a pejotização forçada",
    "pagina": 74
   },
   {
    "titulo": "Trabalho útil para a comunidade",
    "pagina": 74
   }
  ]
 },
 {
  "chave": "comida-e-custo-de-vida",
  "titulo": "Comida na mesa e custo de vida",
  "chamada": "Preço sob controle, juros caindo, menos dívida apertando o orçamento e crédito para quem planta a comida da cesta básica.",
  "propostas": [
   {
    "titulo": "Renda subindo mais que os preços",
    "pagina": 49
   },
   {
    "titulo": "Juros mais baixos",
    "pagina": 49
   },
   {
    "titulo": "Menos dívida e freio nas bets",
    "pagina": 49
   },
   {
    "titulo": "Crédito para quem planta comida",
    "pagina": 59
   },
   {
    "titulo": "Combustível sem susto",
    "pagina": 66
   },
   {
    "titulo": "Cozinhas solidárias e restaurantes populares",
    "pagina": 26
   },
   {
    "titulo": "Proteção social mantida e ampliada",
    "pagina": 18
   }
  ]
 },
 {
  "chave": "educacao",
  "titulo": "Educação",
  "chamada": "Escola em tempo integral, criança lendo na idade certa, internet em todas as escolas e mais ensino técnico perto de casa.",
  "propostas": [
   {
    "titulo": "Escola em tempo integral",
    "pagina": 31
   },
   {
    "titulo": "Criança lendo na idade certa",
    "pagina": 31
   },
   {
    "titulo": "Mais creches",
    "pagina": 31
   },
   {
    "titulo": "Recuperar o que ficou para trás",
    "pagina": 31
   },
   {
    "titulo": "Internet boa em toda escola",
    "pagina": 32
   },
   {
    "titulo": "Professor valorizado",
    "pagina": 33
   },
   {
    "titulo": "Instituto federal no interior e na periferia",
    "pagina": 33
   },
   {
    "titulo": "Universidade pública mais perto",
    "pagina": 33
   }
  ]
 },
 {
  "chave": "seguranca",
  "titulo": "Segurança",
  "chamada": "Governo federal na linha de frente contra o crime organizado, mexendo no bolso das facções e trabalhando junto com estados e prefeituras.",
  "propostas": [
   {
    "titulo": "Ministério da Segurança Pública",
    "pagina": 30
   },
   {
    "titulo": "Asfixiar o dinheiro do crime",
    "pagina": 27
   },
   {
    "titulo": "Contra armas, milícias e facções",
    "pagina": 27
   },
   {
    "titulo": "Bandido fora da eleição",
    "pagina": 27
   },
   {
    "titulo": "Celular Seguro",
    "pagina": 29
   },
   {
    "titulo": "Polícia perto da comunidade",
    "pagina": 30
   },
   {
    "titulo": "Estado presente no bairro",
    "pagina": 28
   }
  ]
 },
 {
  "chave": "moradia-e-bairro",
  "titulo": "Moradia e bairro",
  "chamada": "Casa própria pelo Minha Casa Minha Vida, ajuda para reformar, água e esgoto na periferia e transporte coletivo melhor.",
  "propostas": [
   {
    "titulo": "Minha Casa Minha Vida maior",
    "pagina": 45
   },
   {
    "titulo": "Comprar imóvel já pronto",
    "pagina": 45
   },
   {
    "titulo": "Ajuda para reformar a casa",
    "pagina": 45
   },
   {
    "titulo": "Mais obras nas periferias",
    "pagina": 46
   },
   {
    "titulo": "Água tratada e esgoto",
    "pagina": 46
   },
   {
    "titulo": "Ônibus, metrô e trem",
    "pagina": 46
   }
  ]
 },
 {
  "chave": "aposentados-e-idosos",
  "titulo": "Aposentados e pessoas idosas",
  "chamada": "Fila do INSS menor, cuidado em casa para quem tem dificuldade de sair e proteção contra golpe no celular.",
  "propostas": [
   {
    "titulo": "Fila do INSS menor",
    "pagina": 77
   },
   {
    "titulo": "Médico em casa para o idoso",
    "pagina": 22
   },
   {
    "titulo": "Centros-Dia e lugares para conviver",
    "pagina": 22
   },
   {
    "titulo": "Trabalho depois dos 60",
    "pagina": 23
   },
   {
    "titulo": "Proteção contra golpe digital",
    "pagina": 23
   },
   {
    "titulo": "Formação de cuidadores",
    "pagina": 26
   }
  ]
 },
 {
  "chave": "mulheres",
  "titulo": "Mulheres",
  "chamada": "Mais lugares para acolher a mulher ameaçada, agressor vigiado de perto, salário igual e saúde cuidada em todas as fases da vida.",
  "propostas": [
   {
    "titulo": "Casas da Mulher Brasileira",
    "pagina": 21
   },
   {
    "titulo": "Agressor monitorado",
    "pagina": 21
   },
   {
    "titulo": "Salário igual para mulheres",
    "pagina": 75
   },
   {
    "titulo": "Empresa terá que corrigir diferença",
    "pagina": 75
   },
   {
    "titulo": "Cuidotecas para as crianças",
    "pagina": 26
   },
   {
    "titulo": "Exame e cuidado na saúde da mulher",
    "pagina": 38
   },
   {
    "titulo": "Absorvente de graça",
    "pagina": 38
   }
  ]
 },
 {
  "chave": "juventude",
  "titulo": "Juventude e infância",
  "chamada": "Jovem estudando sem precisar largar a escola por dinheiro, caminho para o primeiro emprego e criança protegida na internet.",
  "propostas": [
   {
    "titulo": "Pé-de-Meia continua",
    "pagina": 32
   },
   {
    "titulo": "Cursinho popular para a faculdade",
    "pagina": 24
   },
   {
    "titulo": "Comida e moradia para universitário",
    "pagina": 24
   },
   {
    "titulo": "Primeiro emprego como aprendiz",
    "pagina": 24
   },
   {
    "titulo": "Jovem empreendedor e jovem do campo",
    "pagina": 25
   },
   {
    "titulo": "Saúde mental dos jovens",
    "pagina": 25
   },
   {
    "titulo": "Criança protegida na internet",
    "pagina": 24
   }
  ]
 },
 {
  "chave": "pequenos-negocios",
  "titulo": "Pequenos negócios e quem trabalha por conta",
  "chamada": "Crédito mais fácil, menos papelada e chance de vender para o governo, para o pequeno empresário, o autônomo e a cooperativa do bairro.",
  "propostas": [
   {
    "titulo": "Menos burocracia e vender para o governo",
    "pagina": 57
   },
   {
    "titulo": "Crédito com garantia do governo",
    "pagina": 58
   },
   {
    "titulo": "Brasil Mais Produtivo maior",
    "pagina": 58
   },
   {
    "titulo": "Apoio ao autônomo",
    "pagina": 76
   },
   {
    "titulo": "Cooperativas populares",
    "pagina": 76
   },
   {
    "titulo": "Tecnologia para o pequeno",
    "pagina": 55
   }
  ]
 },
 {
  "chave": "campo",
  "titulo": "Campo e agricultura familiar",
  "chamada": "Crédito mais simples para quem produz, proteção quando o clima castiga a lavoura, água no semiárido e internet chegando ao campo.",
  "propostas": [
   {
    "titulo": "Crédito com menos papelada",
    "pagina": 59
   },
   {
    "titulo": "Crédito para jovens e mulheres do campo",
    "pagina": 59
   },
   {
    "titulo": "Garantia-Safra e seguro rural",
    "pagina": 60
   },
   {
    "titulo": "Cisternas no semiárido",
    "pagina": 60
   },
   {
    "titulo": "Reforma agrária",
    "pagina": 60
   },
   {
    "titulo": "Plano Safra para quem produz",
    "pagina": 61
   },
   {
    "titulo": "Internet e 5G no campo",
    "pagina": 55
   }
  ]
 },
 {
  "chave": "meio-ambiente",
  "titulo": "Meio ambiente e clima",
  "chamada": "Floresta de pé, cidade mais preparada para enchente e deslizamento, água garantida e cuidado com os bichos.",
  "propostas": [
   {
    "titulo": "Desmatamento zero",
    "pagina": 70
   },
   {
    "titulo": "Obras contra enchente e deslizamento",
    "pagina": 47
   },
   {
    "titulo": "Prevenir desastres",
    "pagina": 72
   },
   {
    "titulo": "Água para beber e produzir",
    "pagina": 72
   },
   {
    "titulo": "Castração de cães e gatos",
    "pagina": 71
   },
   {
    "titulo": "Satélite contra crime ambiental",
    "pagina": 72
   }
  ]
 }
]'''

AVISOS = []


def log(*a):
    print(*a, file=sys.stderr)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def pct(a, d, casas=1):
    return round(a / d * 100, casas) if d else None


def br(n, casas=0):
    """Formata número no padrão pt-BR (4.558 / 8,9)."""
    t = f"{n:,.{casas}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def razao(a, d):
    return round(a / d, 2) if d else None


# ---- HTTP -------------------------------------------------------------------
def http_json(url, tentativas=3, timeout=30):
    """GET + json. 404/HTML -> None. Erros de rede: tenta de novo e registra aviso."""
    erro = "?"
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                return json.loads(raw)
            except ValueError:
                return None  # 404 do Vercel vem como HTML "NOT_FOUND"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            erro = f"HTTP {e.code}"
        except Exception as e:  # timeout, DNS, conexão
            erro = str(e)
        time.sleep(1.5 * (i + 1))
    AVISOS.append(f"falha ao buscar {url}: {erro}")
    return None


# ---- localizar a cidade -----------------------------------------------------
UF_NOMES = {"RS": "Rio Grande do Sul", "SP": "São Paulo", "MG": "Minas Gerais",
            "BA": "Bahia", "PR": "Paraná", "PE": "Pernambuco", "CE": "Ceará",
            "RJ": "Rio de Janeiro", "SC": "Santa Catarina", "MA": "Maranhão",
            "GO": "Goiás", "PA": "Pará", "AM": "Amazonas", "PI": "Piauí",
            "RN": "Rio Grande do Norte", "AL": "Alagoas", "PB": "Paraíba",
            "SE": "Sergipe", "ES": "Espírito Santo", "MT": "Mato Grosso",
            "MS": "Mato Grosso do Sul", "RO": "Rondônia", "TO": "Tocantins",
            "AC": "Acre", "AP": "Amapá", "RR": "Roraima", "DF": "Distrito Federal"}


def parse_entrada(texto, uf=None):
    m = re.match(r"^\s*(.+?)\s*[,/–-]\s*([A-Za-z]{2})\s*$", texto)
    if m:
        return m.group(1).strip(), m.group(2).upper()
    if uf:
        return texto.strip(), uf.upper()
    sys.exit('Informe cidade e UF, ex.: "Cachoeira do Sul, RS"')


def encontrar_cidade(nome, uf):
    """(lat, lon, eleitorado_TSE|None, nome_oficial)."""
    alvo = norm(nome)
    prefixos = []
    for k in (4, 3, 2):
        p = alvo.replace(" ", "")[:k]
        if len(p) >= 2 and p not in prefixos:
            prefixos.append(p)
    for p in prefixos:
        d = http_json(f"{BASE}/dados/busca/{urllib.parse.quote(p)}.json", tentativas=1)
        if isinstance(d, list):
            for c in d:
                if c.get("t") == "m" and norm(c.get("n")) == alvo and c.get("uf") == uf:
                    return c["lat"], c["lon"], c.get("e"), c.get("n", nome)
    q = f"{nome}, {UF_NOMES.get(uf, uf)}, Brasil"
    d = http_json("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br&q="
                  + urllib.parse.quote(q))
    if isinstance(d, list) and d and d[0].get("lat"):
        AVISOS.append("cidade não achada na busca do app; coordenadas do Nominatim, sem total do TSE")
        return float(d[0]["lat"]), float(d[0]["lon"]), None, nome
    return None


# ---- quadriculado de tiles --------------------------------------------------
def tile_de(lat, lon, tam):
    k = round(1 / tam)  # igual ao app: floor(lat * células por grau)
    return f"{math.floor(lat * k)}_{math.floor(lon * k)}"


def tiles_ao_redor(lat, lon, r, tam):
    k = round(1 / tam)
    la0, lo0 = math.floor(lat * k), math.floor(lon * k)
    return [f"{la}_{lo}" for la in range(la0 - r, la0 + r + 1)
            for lo in range(lo0 - r, lo0 + r + 1)]


def coletar_celulas(lat, lon, nome, uf, max_r, tam):
    """Varre anéis crescentes de tiles até um anel não trazer célula nova."""
    alvo, cache, ant = norm(nome), {}, -1
    celulas = {}
    for r in range(1, max_r + 1):
        for t in tiles_ao_redor(lat, lon, r, tam):
            if t not in cache:
                cache[t] = http_json(f"{BASE}/dados/celulas/{t}.json")
        celulas = {}
        for t in tiles_ao_redor(lat, lon, r, tam):
            for c in cache[t] or []:
                if (isinstance(c, dict) and "id" in c and c.get("uf") == uf
                        and norm(c.get("municipio")) == alvo):
                    celulas[c["id"]] = c
        log(f"  varredura r={r}: {len(celulas)} regiões")
        if celulas and len(celulas) == ant:
            return list(celulas.values()), r
        ant = len(celulas)
    if celulas:
        AVISOS.append(f"varredura não convergiu até r={max_r}; pode faltar região de borda (use --max-raio maior)")
    return list(celulas.values()), max_r


def coletar_perfil(celulas, tam):
    ids = {c["id"] for c in celulas}
    out = {}
    for t in sorted({tile_de(c["lat"], c["lon"], tam) for c in celulas}):
        d = http_json(f"{BASE}/dados/perfil2022/{t}.json")
        if isinstance(d, dict):
            itens = d.items()
        elif isinstance(d, list):
            itens = ((x.get("id"), x) for x in d if isinstance(x, dict))
        else:
            itens = []
        for k, v in itens:
            if k in ids:
                out[k] = v
    return out


def coletar_marcas(ids):
    out = {}
    for i in range(0, len(ids), 60):
        d = http_json(f"{BASE}/api/marcas?regioes=" + ",".join(ids[i:i + 60]))
        if isinstance(d, dict):
            out.update(d)
    return out


# ---- materiais do app -------------------------------------------------------
def carregar_json(caminho):
    if caminho and os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return None


def indexar_temas(propostas):
    """{id: {titulo, chamada, n_propostas, propostas}} a partir de propostas-temas.json."""
    temas = {k: {"titulo": v, "n_propostas": None, "chamada": None, "propostas": []}
             for k, v in TITULOS_TEMAS.items()}
    if isinstance(propostas, dict):
        propostas = propostas.get("temas", list(propostas.values()))
    for t in propostas or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("slug") or t.get("chave") or slugify(t.get("titulo") or t.get("nome") or "")
        if not tid:
            continue
        titulo = t.get("titulo") or t.get("nome") or t.get("title") or temas.get(tid, {}).get("titulo") or tid
        props = t.get("propostas") if isinstance(t.get("propostas"), list) else []
        temas[tid] = {"titulo": titulo, "chamada": t.get("chamada"), "n_propostas": len(props) or None,
                      "propostas": [{"titulo": x.get("titulo"), "pagina": x.get("pagina")}
                                    for x in props if isinstance(x, dict)]}
    return temas


def temas_da_ponte(tema):
    """Liga o texto livre do `tema` de uma ponte aos ids dos 12 temas."""
    n = norm(tema)
    return [tid for tid, chaves in PALAVRAS_TEMA if any(k in n for k in chaves)]


def indexar_fichas(fichas_json):
    out = {}
    for f in (fichas_json or {}).get("fichas", []):
        if isinstance(f, dict):
            chave = f.get("chave") or f.get("id") or f.get("slug")
            if chave:
                out[norm(chave)] = f
    return out


def material_da_ficha(f):
    """Recorte de uma ficha para o JSON de saída (sem as citações longas)."""
    if not f:
        return None
    if f.get("tipo") == "voto":
        return {k: f.get(k) for k in ("titulo", "frase", "apoio", "explicacao", "roteiro", "cuidado")}
    return {
        "titulo": f.get("titulo"),
        "abertura": f.get("abertura"),
        "pontes": [{"tema": p.get("tema"), "tipo": p.get("tipo"), "em_comum": p.get("emComum"),
                    "temas_propostas": temas_da_ponte(p.get("tema", ""))}
                   for p in f.get("pontes", []) if isinstance(p, dict)],
    }


# ---- análise ----------------------------------------------------------------
def analisar(celulas, perfil, marcas, nomes, tse, fichas, temas):
    tot = collections.Counter()
    cand = collections.Counter()
    falhas_identidade = []
    parciais = []
    por_bairro = collections.defaultdict(collections.Counter)
    l22 = collections.Counter()

    for c in celulas:
        v = c["votos"]
        outros = {str(k): int(x) for k, x in (v.get("outros") or {}).items()}
        validos = v["lula"] + v["flavio"] + sum(outros.values())
        if c["eleitores"] - (validos + v["brancos"] + v["nulos"]) != v["abstencao"]:
            falhas_identidade.append(c["id"])
        if c.get("apuradas", 0) < c.get("urnas", 0):
            parciais.append({"id": c["id"], "bairro": c.get("bairro"),
                             "urnas": c.get("urnas"), "apuradas": c.get("apuradas")})
        for k, x in (("eleitores", c["eleitores"]), ("urnas", c.get("urnas", 0)),
                     ("apuradas", c.get("apuradas", 0)), ("brancos", v["brancos"]),
                     ("nulos", v["nulos"]), ("abstencao", v["abstencao"]),
                     ("validos", validos)):
            tot[k] += x
        cand[LULA] += v["lula"]
        cand[FLAVIO] += v["flavio"]
        cand.update(outros)
        if isinstance(c.get("lula2022"), (int, float)) and c.get("apuradas", 0) >= c.get("urnas", 0):
            l22["regioes"] += 1
            l22["lula2022"] += c["lula2022"]
            l22["lula2026"] += v["lula"]
        b = por_bairro[c.get("bairro") or "(sem bairro)"]
        b["regioes"] += 1
        b["eleitores"] += c["eleitores"]
        b["validos"] += validos
        b["abstencao"] += v["abstencao"]
        b["brancos"] += v["brancos"]
        b["nulos"] += v["nulos"]
        b["c" + LULA] += v["lula"]
        b["c" + FLAVIO] += v["flavio"]
        for k, x in outros.items():
            b["c" + k] += x

    el, val = tot["eleitores"], tot["validos"]
    lula, flav = cand[LULA], cand[FLAVIO]
    outros_total = val - lula - flav
    # comparecimento pelos votos de fato (em região com urna ainda sem boletim,
    # "eleitores" inclui a urna faltante e eleitorado − abstenção superestima)
    comparecimento = val + tot["brancos"] + tot["nulos"]

    def nome(k):
        return nomes.get(k) or NOMES_PADRAO.get(k) or f"número {k}"

    # ---- bairros
    bairros = []
    for nb, b in por_bairro.items():
        lp, fp = pct(b["c" + LULA], b["validos"]), pct(b["c" + FLAVIO], b["validos"])
        ab = pct(b["abstencao"], b["eleitores"])
        dif = (fp or 0) - (lp or 0)
        if dif < 0:
            cat = "base_a_segurar"
        elif dif <= LIMIAR_COMPETITIVO_PP:
            cat = "periferia_conversavel"
        else:
            cat = "terreno_de_flavio"
        bairros.append({
            "bairro": nb, "regioes": b["regioes"], "eleitorado": b["eleitores"],
            "votos_validos": b["validos"], "lula": b["c" + LULA], "flavio": b["c" + FLAVIO],
            "lula_pct_validos": lp, "flavio_pct_validos": fp,
            "vantagem_flavio_pp": round(dif, 1),
            "abstencao": b["abstencao"], "abstencao_pct_eleitorado": ab,
            "brancos": b["brancos"], "nulos": b["nulos"],
            "ponte": {NOME_CURTO[k]: b["c" + k] for k in PONTE},
            "categoria": cat, "abstencao_alta": (ab or 0) >= LIMIAR_ABSTENCAO_ALTA,
            "_c": b,
        })
    bairros.sort(key=lambda x: -x["eleitorado"])

    def top(chave, filtro=None, n=TOP_ONDE):
        lst = [b for b in bairros if (filtro is None or filtro(b))]
        lst.sort(key=chave, reverse=True)
        return [b["bairro"] for b in lst[:n]]

    # ---- a conta
    dif = flav - lula
    lider = "Flávio" if dif > 0 else ("Lula" if dif < 0 else "empate")
    metade = abs(dif) / 2
    ponte = sum(cand[k] for k in PONTE)
    bn = tot["brancos"] + tot["nulos"]
    total_pool = ponte + bn + tot["abstencao"]
    vant_pp = round(pct(abs(dif), val, 2) or 0, 1)

    def mx(a):
        return br(a / metade, 1) + "×" if metade else "—"

    # Regra do template: cidade de Lula se Lula lidera; fortaleza se Flávio está
    # bem à frente E nem 100% dos bolsões de ponte cobrem a metade; senão, empate.
    if dif <= 0:
        tipo, rotulo = "cidade_de_lula", "Cidade de Lula"
        expl = (f"Lula lidera por {br(abs(dif))} votos ({br(vant_pp, 1)}pp). O trabalho é segurar o "
                f"comparecimento no dia 25 e crescer na abstenção ({br(tot['abstencao'])} pessoas) "
                f"e nos bairros onde Flávio ganhou.")
    elif vant_pp <= LIMIAR_EMPATE_PP or ponte >= metade:
        tipo, rotulo = "cidade_de_empate", "Cidade de empate"
        expl = (f"Flávio lidera por {br(dif)} votos ({br(vant_pp, 1)}pp); faltam {br(metade)} votos "
                f"líquidos pra empatar. Os bolsões de ponte ({br(ponte)}) valem {mx(ponte)} a metade: "
                f"convertê-los já pode virar a cidade. A abstenção ({br(tot['abstencao'])}) vale {mx(tot['abstencao'])}.")
    else:
        tipo, rotulo = "fortaleza_de_flavio", "Fortaleza de Flávio"
        expl = (f"Flávio lidera por {br(dif)} votos ({br(vant_pp, 1)}pp); faltam {br(metade)} votos "
                f"líquidos pra empatar. Os bolsões de ponte ({br(ponte)}) valem só {mx(ponte)} a metade — "
                f"nem 100% deles basta. A cidade se move pela abstenção ({br(tot['abstencao'])}, "
                f"{mx(tot['abstencao'])} a metade) e por virar votos de Flávio na periferia conversável "
                f"(cada voto trocado conta dobrado).")

    # ---- perfil de abstenção por segmento (2º turno de 2022)
    seg = collections.defaultdict(lambda: [0, 0])
    for p in perfil.values():
        for d in p.get("destaques", []) if isinstance(p, dict) else []:
            g = d.get("g")
            if g:
                seg[g][0] += d.get("inscritos", 0)
                seg[g][1] += d.get("abstencao", 0)
    if not perfil:
        AVISOS.append("nenhum perfil por segmento carregado (perfil_eleitor vazio)")
    aptos22 = sum(p.get("aptos", 0) for p in perfil.values() if isinstance(p, dict))
    abst22 = sum(p.get("abstencao", 0) for p in perfil.values() if isinstance(p, dict))
    perfil_out = {
        "referencia": "2º turno de 2022 (Lula x Bolsonaro)",
        "nota": ("Quem costumava faltar: abstenção total por seção é contada pelo TSE; a divisão "
                 "por grupo (70+, fundamental incompleto etc.) é estimada pelo app. Para a "
                 "abstenção de 2026, use numeros_absolutos/regioes."),
        "regioes_com_perfil": len(perfil), "regioes_total": len(celulas),
        "aptos_2022": aptos22, "abstencao_2022": abst22, "abstencao_2022_pct": pct(abst22, aptos22),
        "segmentos": {g: {"inscritos": i, "abstencao": a, "abstencao_pct": pct(a, i, 0)}
                      for g, (i, a) in sorted(seg.items())},
    }

    # ---- temas das pautas
    def temas_da_pauta(pid):
        f = fichas.get(pid)
        ids = []
        if f and isinstance(f.get("pontes"), list):
            for pt in f["pontes"]:
                for tid in temas_da_ponte(pt.get("tema", "") if isinstance(pt, dict) else str(pt)):
                    if tid not in ids:
                        ids.append(tid)
        return ids or list(TEMAS_POR_PAUTA.get(pid, []))

    # ---- ranking
    pautas = [{
        "id": "abstencao", "pauta": "Quem não foi votar", "publico": tot["abstencao"],
        "acao": "trazer para votar no dia 25",
        "material": material_da_ficha(fichas.get("abstencao")),
        # bairros com abstenção alta (≥ limiar), ordenados por quantas pessoas faltaram
        "onde": top(lambda b: b["abstencao"], lambda b: b["abstencao_alta"])
                or top(lambda b: b["abstencao"]),
    }]
    for k, fid in PONTE.items():
        if cand[k] > 0:
            pautas.append({
                "id": fid, "pauta": f"Quem votou no {NOME_CURTO[k]}", "candidato": nome(k),
                "publico": cand[k], "pct_validos": pct(cand[k], val), "acao": "converter (ponte)",
                "material": material_da_ficha(fichas.get(fid)),
                "onde": top(lambda b, k=k: b["_c"]["c" + k]),
            })
    pautas += [
        {"id": "branco", "pauta": "Quem votou em branco", "publico": tot["brancos"],
         "acao": "converter", "material": material_da_ficha(fichas.get("branco")),
         "onde": top(lambda b: b["brancos"])},
        {"id": "nulo", "pauta": "Quem anulou o voto", "publico": tot["nulos"],
         "acao": "converter", "material": material_da_ficha(fichas.get("nulo")),
         "onde": top(lambda b: b["nulos"])},
    ]
    demais = {k: v for k, v in cand.items() if k not in PONTE and k not in (LULA, FLAVIO) and v}
    if demais:
        pautas.append({"id": "demais", "pauta": "Demais candidatos", "publico": sum(demais.values()),
                       "candidatos": {nome(k): v for k, v in sorted(demais.items(), key=lambda x: -x[1])},
                       "acao": "converter (roteiro geral)", "material": None,
                       "onde": top(lambda b, ks=tuple(demais): sum(b["_c"]["c" + k] for k in ks))})
    pautas = [p for p in pautas if p["publico"] > 0]
    pautas.sort(key=lambda p: -p["publico"])  # ordem estatística
    pautas += [
        {"id": "converter-flavio", "pauta": "Eleitores de Flávio (converter)", "publico": flav,
         "acao": "converter nos bairros competitivos (cada voto trocado conta dobrado)", "material": None,
         "onde": top(lambda b: b["flavio"], lambda b: b["categoria"] == "periferia_conversavel")},
        {"id": "segurar-lula", "pauta": "Eleitores de Lula (segurar)", "publico": lula,
         "acao": "confirmar comparecimento no dia 25", "material": None,
         "onde": top(lambda b: b["lula"], lambda b: b["categoria"] == "base_a_segurar")},
    ]
    campos = ("posicao", "id", "pauta", "candidato", "candidatos", "publico", "pct_eleitorado",
              "pct_validos", "multiplo_da_metade", "acao", "onde", "temas", "material")
    for i, p in enumerate(pautas, 1):
        p["posicao"] = i
        p["pct_eleitorado"] = pct(p["publico"], el)
        p["multiplo_da_metade"] = razao(p["publico"], metade)
        p["temas"] = temas_da_pauta(p["id"])
    pautas = [{k: p[k] for k in campos if k in p} for p in pautas]

    # ---- temas para abrir nas Propostas
    peso = collections.Counter()
    for p in pautas:
        for tid in p["temas"]:
            peso[tid] += p["publico"]

    def info_tema(t):
        return {"id": t, "titulo": temas.get(t, {}).get("titulo", t)}

    temas_out = {
        "por_pauta": [{"id_pauta": p["id"], "pauta": p["pauta"],
                       "temas": [info_tema(t) for t in p["temas"]]} for p in pautas],
        "por_relevancia": [dict(info_tema(t), chamada=temas.get(t, {}).get("chamada"),
                                n_propostas=temas.get(t, {}).get("n_propostas"),
                                propostas=temas.get(t, {}).get("propostas", []),
                                publico_alcancado=w,
                                pautas=[p["id"] for p in pautas if t in p["temas"]])
                           for t, w in peso.most_common()],
    }

    for b in bairros:
        del b["_c"]
    nz = {k: v for k, v in marcas.items() if v}
    bairro_de = {c["id"]: c.get("bairro") or "(sem bairro)" for c in celulas}
    marcas_bairro = collections.Counter()
    for k, v in nz.items():
        marcas_bairro[bairro_de.get(k, "(região fora da cidade)")] += v

    comp_2022 = None
    if l22["regioes"]:
        comp_2022 = {
            "referencia": "Lula no 2º turno de 2022 x Lula no 1º turno de 2026, nas mesmas regiões",
            "nota": ("Mesma conta do app ('Em 2022, no 2º turno, o Lula teve X votos a mais por aqui'), "
                     "só que somando a cidade inteira; regiões com urna sem boletim ficam de fora."),
            "regioes_com_dado": l22["regioes"],
            "lula_2022_2turno": l22["lula2022"],
            "lula_2026_1turno": l22["lula2026"],
            "votos_a_mais_em_2022": l22["lula2022"] - l22["lula2026"],
            "variacao_pct": pct(l22["lula2026"] - l22["lula2022"], l22["lula2022"]),
        }

    return {
        "numeros_absolutos": {
            "eleitorado": el, "eleitorado_tse": tse,
            "diferenca_tse": (tse - el) if tse else None,
            "regioes": len(celulas), "bairros": len(bairros),
            "urnas": tot["urnas"], "urnas_apuradas": tot["apuradas"],
            "comparecimento": comparecimento, "abstencao": tot["abstencao"],
            "votos_validos": val, "brancos": tot["brancos"], "nulos": tot["nulos"],
            "lula": lula, "flavio": flav, "outros": outros_total,
            "regioes_flavio_vence": sum(1 for c in celulas if c["votos"]["flavio"] > c["votos"]["lula"]),
            "bairros_flavio_vence": sum(1 for b in bairros if b["flavio"] > b["lula"]),
        },
        "percentuais": {
            "comparecimento_pct_eleitorado": pct(comparecimento, el),
            "abstencao_pct_eleitorado": pct(tot["abstencao"], el),
            "brancos_pct_comparecimento": pct(tot["brancos"], comparecimento),
            "nulos_pct_comparecimento": pct(tot["nulos"], comparecimento),
            "lula_pct_validos": pct(lula, val), "flavio_pct_validos": pct(flav, val),
            "outros_pct_validos": pct(outros_total, val),
            "apuracao_pct": pct(tot["apuradas"], tot["urnas"]),
        },
        "votos_por_candidato": [
            {"numero": k, "nome": nome(k), "votos": v, "pct_validos": pct(v, val, 2),
             "ponte": k in PONTE}
            for k, v in sorted(cand.items(), key=lambda x: -x[1]) if v
        ],
        "comparacao_lula_2022": comp_2022,
        "conta": {
            "lider": lider, "diferenca": abs(dif), "vantagem_pp": vant_pp,
            "metade_para_empatar": round(metade),
            "bolsoes": {
                "ponte": {"votos": ponte, "multiplo_da_metade": razao(ponte, metade),
                          "detalhe": {NOME_CURTO[k]: cand[k] for k in PONTE}},
                "branco_nulo": {"votos": bn, "multiplo_da_metade": razao(bn, metade)},
                "abstencao": {"votos": tot["abstencao"], "multiplo_da_metade": razao(tot["abstencao"], metade)},
                "total": {"votos": total_pool, "multiplo_da_metade": razao(total_pool, metade)},
            },
        },
        "classificacao": {"tipo": tipo, "rotulo": rotulo, "explicacao": expl},
        "perfil_eleitor": perfil_out,
        "regioes": {
            "bairros": bairros,
            "periferia_conversavel": [b["bairro"] for b in bairros if b["categoria"] == "periferia_conversavel"],
            "base_a_segurar": [b["bairro"] for b in bairros if b["categoria"] == "base_a_segurar"],
            "terreno_de_flavio": [b["bairro"] for b in bairros if b["categoria"] == "terreno_de_flavio"],
            "abstencao_alta": [b["bairro"] for b in bairros if b["abstencao_alta"]],
        },
        "situacao_no_app": {"regioes_consultadas": len(marcas), "regioes_com_marca": len(nz),
                            "pessoas_cadastradas": sum(nz.values()),
                            "territorio_aberto": sum(nz.values()) <= 1,
                            "por_bairro": dict(sorted(marcas_bairro.items(), key=lambda x: -x[1])),
                            "marcas": nz},
        "ranking_das_pautas": pautas,
        "temas_para_abrir_nas_propostas": temas_out,
        "checagens": {
            "falhas_identidade_abstencao": falhas_identidade,
            "regioes_com_urna_sem_boletim": parciais,
            "nota": ("Identidade: eleitores − (válidos + brancos + nulos) == abstenção. Falha esperada em "
                     "região com urna sem boletim (o eleitorado conta a urna, os votos não)."),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Pauta de conversas (2º turno) de um município, em JSON.")
    ap.add_argument("cidade", help='ex.: "Cachoeira do Sul, RS"')
    ap.add_argument("--uf", help="UF, se não vier junto do nome")
    ap.add_argument("-o", "--saida", help="arquivo JSON de saída (padrão: <cidade>-<uf>.json na pasta atual; "
                         "o JSON também sai no stdout)")
    ap.add_argument("--dados", default="dados/app",
                    help="pasta com fichas-conversas.json / propostas-temas.json (opcional)")
    ap.add_argument("--celulas", help="arquivo local de células (pula a busca online; ex.: tirado de um HAR)")
    ap.add_argument("--perfil", help="arquivo local perfil2022 (2º turno de 2022) (opcional, com --celulas)")
    ap.add_argument("--marcas", help="arquivo local de marcas (opcional, com --celulas)")
    ap.add_argument("--salvar-dados", action="store_true",
                    help="grava celulas/totais/perfil2022/marcas-<slug>.json em --dados")
    ap.add_argument("--max-raio", type=int, default=4, help="raio máximo da varredura de tiles")
    args = ap.parse_args()

    nome, uf = parse_entrada(args.cidade, args.uf)
    tse, lat, lon, raio, indice = None, None, None, None, {}

    if args.celulas:
        log(f"modo offline: {args.celulas}")
        bruto = carregar_json(args.celulas)
        if bruto is None:
            sys.exit(f"arquivo não encontrado: {args.celulas}")
        bruto = bruto if isinstance(bruto, list) else list(bruto.values())
        alvo = norm(nome)
        celulas = [c for c in bruto if norm(c.get("municipio")) == alvo and c.get("uf") == uf]
        if not celulas:
            sys.exit(f"nenhuma região de {nome}/{uf} em {args.celulas}")
        nome_oficial = celulas[0]["municipio"]
        lat = round(sum(c["lat"] for c in celulas) / len(celulas), 5)
        lon = round(sum(c["lon"] for c in celulas) / len(celulas), 5)
        perfil = carregar_json(args.perfil) or {}
        perfil = {k: v for k, v in perfil.items() if k in {c["id"] for c in celulas}}
        marcas = carregar_json(args.marcas) or {}
        if not args.marcas:
            AVISOS.append("modo offline sem --marcas: situação no app não consultada")
        AVISOS.append("modo offline: sem total do TSE para conferir o eleitorado")
    else:
        log(f"buscando {nome} ({uf})…")
        info = encontrar_cidade(nome, uf)
        if not info:
            sys.exit(f"cidade não encontrada: {nome}/{uf}" + (" — " + "; ".join(AVISOS) if AVISOS else ""))
        lat, lon, tse, nome_oficial = info
        log(f"  lat={lat} lon={lon} eleitorado TSE={tse}")
        indice = http_json(f"{BASE}/dados/indice.json") or {}
        tam = float(indice.get("celula") or TAMANHO_TILE_PADRAO)
        celulas, raio = coletar_celulas(lat, lon, nome_oficial, uf, args.max_raio, tam)
        if not celulas:
            sys.exit(f"nenhuma região encontrada para {nome_oficial}/{uf} " + "; ".join(AVISOS))
        perfil = coletar_perfil(celulas, tam)
        marcas = coletar_marcas([c["id"] for c in celulas])

    nomes = {str(k): v for k, v in (indice.get("candidatos") or {}).items()}
    fichas_json = carregar_json(os.path.join(args.dados, "fichas-conversas.json"))
    fonte_fichas = "arquivo local" if fichas_json else "cópia embutida no script"
    fichas_json = fichas_json or json.loads(FICHAS_EMBUTIDAS)
    fichas = indexar_fichas(fichas_json)
    propostas_json = carregar_json(os.path.join(args.dados, "propostas-temas.json"))
    fonte_propostas = "arquivo local" if propostas_json else "cópia embutida no script"
    temas = indexar_temas(propostas_json or json.loads(PROPOSTAS_EMBUTIDAS))

    analise = analisar(celulas, perfil, marcas, nomes, tse, fichas, temas)
    slug = slugify(nome_oficial)
    resultado = {
        "cidade": nome_oficial,
        "uf": uf,
        "slug": slug,
        "coordenadas": {"lat": lat, "lon": lon},
        "snapshot": {"data": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                     "versao_dado": indice.get("versao"), "gerado_em_app": indice.get("geradoEm"),
                     "raio_varredura": raio, "fonte_celulas": args.celulas or BASE,
                     "fichas": fonte_fichas, "propostas": fonte_propostas},
        **analise,
        "roteiro_geral": fichas_json.get("roteiro_geral", []),
        "avisos": AVISOS,
    }

    if args.salvar_dados:
        os.makedirs(args.dados, exist_ok=True)
        tot = {k: resultado["numeros_absolutos"][k] for k in
               ("eleitorado", "urnas", "urnas_apuradas", "brancos", "nulos", "abstencao",
                "lula", "flavio", "outros", "votos_validos")}
        for nomearq, obj in (("celulas", celulas), ("totais", tot),
                             ("perfil2022", perfil), ("marcas", marcas)):
            with open(os.path.join(args.dados, f"{nomearq}-{slug}.json"), "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=1)
        log(f"  dados gravados em {args.dados}/ (slug={slug})")

    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    saida = args.saida or f"{slug}-{uf.lower()}.json"
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    log(f"JSON gravado em {saida}")
    print(texto)


if __name__ == "__main__":
    main()
