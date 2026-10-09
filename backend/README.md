# API de geração de pautas

O frontend envia os dados para `POST /api/pautas`. A API consulta os dados da
cidade, monta o documento e devolve o PDF como download.

## Execução

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Se o Chromium já estiver instalado no servidor, defina `CHROMIUM_PATH` com o
caminho do executável. Em produção, configure `CORS_ORIGINS` com a URL pública
do frontend, sem barra no final.

No frontend, defina:

```bash
VITE_API_URL=https://api.exemplo.com
```

Sem `VITE_API_URL`, o frontend usa `/api/pautas` no mesmo domínio.
