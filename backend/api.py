"""API HTTP para gerar as pautas em PDF usando os scripts do projeto."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.background import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MAX_LOGO_BYTES = 5 * 1024 * 1024
CITY_PATTERN = re.compile(r"^.+?\s*[,/–-]\s*[A-Za-z]{2}\s*$")
ALLOWED_TEXTURES = {"none", "paper", "red"}
ALLOWED_LOGOS = {"image/png", "image/svg+xml"}

app = FastAPI(title="Pauta PDF API", version="1.0.0")

origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def run(command: list[str], cwd: Path, timeout: int) -> None:
    environment = os.environ.copy()
    if "CHROMIUM_PATH" not in environment and Path("/usr/bin/chromium").exists():
        environment["CHROMIUM_PATH"] = "/usr/bin/chromium"
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise HTTPException(
            status_code=504,
            detail="A geração ultrapassou o tempo limite. Tente novamente em alguns minutos.",
        ) from error

    if process.returncode != 0:
        detail = process.stderr.strip().splitlines()
        message = detail[-1] if detail else "O gerador terminou com erro."
        raise HTTPException(status_code=422, detail=message[:500])


def sanitized_svg(raw: bytes) -> bytes:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise HTTPException(status_code=422, detail="O arquivo SVG enviado é inválido.") from error

    blocked = {"script", "foreignObject", "iframe", "object", "embed"}
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] in blocked:
                parent.remove(child)
        for attribute in list(parent.attrib):
            local_name = attribute.rsplit("}", 1)[-1].lower()
            value = parent.attrib[attribute].strip().lower()
            if local_name.startswith("on") or (
                local_name == "href"
                and not value.startswith(("#", "data:image/"))
            ):
                del parent.attrib[attribute]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


async def logo_data_uri(logo: UploadFile | None) -> str | None:
    if logo is None or not logo.filename:
        return None
    if logo.content_type not in ALLOWED_LOGOS:
        raise HTTPException(status_code=415, detail="O logotipo deve estar em SVG ou PNG.")

    raw = await logo.read(MAX_LOGO_BYTES + 1)
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="O logotipo deve ter no máximo 5 MB.")
    if logo.content_type == "image/svg+xml":
        raw = sanitized_svg(raw)
    elif not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="O arquivo PNG enviado é inválido.")

    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{logo.content_type};base64,{encoded}"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/pautas")
async def generate_pauta(
    background_tasks: BackgroundTasks,
    city: str = Form(..., min_length=3, max_length=160),
    content: str = Form("", max_length=20_000),
    texture: str = Form("paper"),
    logo: UploadFile | None = File(None),
) -> FileResponse:
    city = city.strip()
    if not CITY_PATTERN.match(city):
        raise HTTPException(
            status_code=422,
            detail='Informe a cidade com a UF, por exemplo: "Pelotas, RS".',
        )
    if texture not in ALLOWED_TEXTURES:
        raise HTTPException(status_code=422, detail="A textura selecionada é inválida.")

    custom_logo = await logo_data_uri(logo)
    workdir = Path(tempfile.mkdtemp(prefix="pauta-pdf-"))
    json_path = workdir / "pauta.json"
    pdf_path = workdir / "pauta.pdf"

    try:
        run(
            [sys.executable, str(SRC / "pauta_cidade.py"), city, "-o", str(json_path)],
            workdir,
            timeout=180,
        )
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["conteudo_adicional"] = content.strip()
        data["textura"] = texture
        data["logo_customizado"] = custom_logo
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        run(
            [
                sys.executable,
                str(SRC / "render_pauta_pdf.py"),
                str(json_path),
                "-o",
                str(pdf_path),
            ],
            workdir,
            timeout=180,
        )
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise

    background_tasks.add_task(shutil.rmtree, workdir, True)
    filename = f"{data['slug']}-{data['uf'].lower()}-pauta.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        background=background_tasks,
    )
