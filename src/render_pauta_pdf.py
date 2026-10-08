#!/usr/bin/env python3
"""Transforma o JSON do pauta_cidade.py num PDF no estilo cartaz.

uso:
    python3 render_pauta_pdf.py pelotas-rs.json              # -> pelotas-rs.pdf
    python3 render_pauta_pdf.py pelotas-rs.json -o saida.pdf
    python3 render_pauta_pdf.py pelotas-rs.json --html       # também grava o HTML

Dependências: jinja2, playwright, pypdf e pillow
(pip install jinja2 playwright pypdf pillow; playwright install chromium).
O visual fica em templates/: pauta.html.j2 (estrutura), pauta.css (estilo),
fonts/ (Rubik), logo-jpt*.svg, textura-vermelha.jpg (capa e faixas) e
textura-papel.jpg (fundo das páginas internas); as texturas são geradas por textura.py se faltarem.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile

from jinja2 import Environment, FileSystemLoader, StrictUndefined, ChainableUndefined

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(AQUI, "templates")

SEGMENTOS = {
    "18-24": "18 a 24 anos", "25-34": "25 a 34 anos", "35-44": "35 a 44 anos",
    "45-59": "45 a 59 anos", "60-69": "60 a 69 anos", "70+": "70 anos ou mais",
    "fund_incompleto": "Fundamental incompleto", "fund_completo": "Fundamental completo",
    "medio_incompleto": "Médio incompleto", "medio_completo": "Médio completo",
    "superior": "Superior", "analfabeto": "Não alfabetizado", "le_escreve": "Lê e escreve",
}
CATEGORIAS = {
    "base_a_segurar": "Base a segurar",
    "periferia_conversavel": "Periferia conversável",
    "terreno_de_flavio": "Terreno de Flávio",
}


def _br(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def f_n(v):
    """244007 -> 244.007"""
    if v is None or v == "":
        return "—"
    return _br(round(v), 0)


def f_dec(v, casas=1):
    return "—" if v is None else _br(v, casas)


def f_p(v, casas=1, sinal=False, unidade="%"):
    """47.12 -> 47,1%"""
    if v is None:
        return "—"
    s = _br(v, casas) + unidade
    return ("+" + s) if sinal and v > 0 else s.replace("-", "−")


def f_x(v):
    """4.13 -> ×4,1"""
    return "—" if v is None else "×" + _br(v, 1)


def f_data(iso):
    if not iso:
        return "—"
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def montar_html(dados):
    temas = {t["id"]: t["titulo"]
             for t in (dados.get("temas_para_abrir_nas_propostas") or {}).get("por_relevancia", [])}
    pautas = {p["id"]: p["pauta"] for p in dados.get("ranking_das_pautas", [])}
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True,
                      undefined=ChainableUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(
        n=f_n, p=f_p, x=f_x, dec=f_dec, data=f_data,
        segmento=lambda g: SEGMENTOS.get(g, g.replace("_", " ").capitalize()),
        categoria=lambda c: CATEGORIAS.get(c, (c or "").replace("_", " ")),
        tema=lambda t: temas.get(t, t.replace("-", " ").capitalize()),
        pauta=lambda p: pautas.get(p, p),
    )
    return env.get_template("pauta.html.j2").render(d=dados)


def garantir_textura():
    sys.path.insert(0, AQUI)
    vermelha = os.path.join(TEMPLATES, "textura-vermelha.jpg")
    papel = os.path.join(TEMPLATES, "textura-papel.jpg")
    if not os.path.exists(vermelha):
        from textura import gerar
        gerar(vermelha)
    if not os.path.exists(papel):
        from textura import gerar_papel
        gerar_papel(papel)


def aplicar_papel(pdf_path):
    """Põe o papel amassado por baixo de todas as páginas, menos a capa.

    O Chromium não imprime imagem de fundo na margem da página (@page só aceita cor),
    então o fundo entra depois: a textura é gravada uma única vez no PDF e cada página
    interna ganha, no início do seu conteúdo, a ordem de desenhá-la ocupando a folha toda.
    """
    from PIL import Image
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (DecodedStreamObject, DictionaryObject, NameObject,
                               NumberObject, StreamObject)

    caminho = os.path.join(TEMPLATES, "textura-papel.jpg")
    with Image.open(caminho) as im:
        largura, altura = im.size
        modo = im.mode
    imagem = StreamObject()
    imagem._data = open(caminho, "rb").read()
    imagem.update({
        NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
        NameObject("/Width"): NumberObject(largura), NameObject("/Height"): NumberObject(altura),
        NameObject("/ColorSpace"): NameObject("/DeviceRGB" if modo == "RGB" else "/DeviceGray"),
        NameObject("/BitsPerComponent"): NumberObject(8), NameObject("/Filter"): NameObject("/DCTDecode"),
    })

    leitor = PdfReader(pdf_path)
    escritor = PdfWriter(clone_from=leitor)
    ref = escritor._add_object(imagem)
    for i, pagina in enumerate(escritor.pages):
        if i == 0:  # a capa já tem o vermelho dela
            continue
        recursos = pagina.setdefault(NameObject("/Resources"), DictionaryObject()).get_object()
        xobjs = recursos.setdefault(NameObject("/XObject"), DictionaryObject()).get_object()
        xobjs[NameObject("/PapelFundo")] = ref
        pw, ph = float(pagina.mediabox.width), float(pagina.mediabox.height)
        antes = f"q {pw:.2f} 0 0 {ph:.2f} 0 0 cm /PapelFundo Do Q\n".encode()
        conteudo = DecodedStreamObject()
        conteudo.set_data(antes + pagina.get_contents().get_data())
        pagina.replace_contents(conteudo)
        pagina.compress_content_streams()
    with open(pdf_path, "wb") as f:
        escritor.write(f)


def gerar_pdf(html_path, pdf_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        exe = os.environ.get("CHROMIUM_PATH")
        nav = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = nav.new_page()
        pg.goto("file://" + html_path, wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=pdf_path, prefer_css_page_size=True, print_background=True)
        nav.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", help="saída do pauta_cidade.py (ex.: pelotas-rs.json)")
    ap.add_argument("-o", "--saida", help="PDF de saída (padrão: mesmo nome do JSON, .pdf)")
    ap.add_argument("--html", action="store_true", help="grava também o HTML ao lado do PDF")
    args = ap.parse_args()

    with open(args.json, encoding="utf-8") as f:
        dados = json.load(f)
    saida = os.path.abspath(args.saida or os.path.splitext(args.json)[0] + ".pdf")

    garantir_textura()
    html = montar_html(dados)

    # o HTML precisa ficar ao lado do CSS/fontes/textura para os caminhos relativos funcionarem
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=TEMPLATES, delete=False, encoding="utf-8") as tmp:
        tmp.write(html)
        html_tmp = tmp.name
    try:
        gerar_pdf(html_tmp, saida)
        aplicar_papel(saida)
        if args.html:
            destino = os.path.splitext(saida)[0] + ".html"
            shutil.copy(html_tmp, destino)
            print(f"HTML: {destino} (abre corretamente se estiver na pasta templates/)", file=sys.stderr)
    finally:
        os.unlink(html_tmp)
    print(f"PDF gravado em {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
