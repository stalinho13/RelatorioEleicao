"""Vetoriza o logo JPT (raster) em SVG limpo: fundo vermelho, estrela amarela, letras pretas."""
import sys

import numpy as np
import potrace
from PIL import Image, ImageFilter

ORIG, SAIDA, ESCALA = sys.argv[1], sys.argv[2], 4
CORES = {"vermelho": (237, 28, 36), "amarelo": (255, 203, 8), "preto": (35, 31, 32)}

im = Image.open(ORIG).convert("RGB")
w0, h0 = im.size
big = im.resize((w0 * ESCALA, h0 * ESCALA), Image.LANCZOS)
a = np.asarray(big, dtype=np.float32)

nomes = list(CORES)
dist = np.stack([((a - np.array(CORES[n])) ** 2).sum(-1) for n in nomes])
classe = dist.argmin(0)


def suave(mask, raio=2.2):
    """Suaviza a borda serrilhada antes de traçar."""
    img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(raio))
    return np.asarray(img) > 127


preto = suave(classe == nomes.index("preto"))
amarelo_raw = classe == nomes.index("amarelo")
# o amarelo continua por baixo das letras, para não sobrar fresta vermelha na junção
perto = np.asarray(Image.fromarray((amarelo_raw * 255).astype(np.uint8))
                   .filter(ImageFilter.MaxFilter(13))) > 0
amarelo = suave(amarelo_raw | ((classe == nomes.index("preto")) & perto))


def tracar(mask):
    bm = potrace.Bitmap(~mask)  # potracer traça os pixels "escuros" (False)
    plist = bm.trace(turdsize=30, alphamax=1.0, opticurve=True, opttolerance=0.25)
    k = 1 / ESCALA
    partes = []
    for curva in plist:
        x, y = curva.start_point.x * k, curva.start_point.y * k
        d = [f"M{x:.2f} {y:.2f}"]
        for s in curva.segments:
            if s.is_corner:
                d.append(f"L{s.c.x*k:.2f} {s.c.y*k:.2f}L{s.end_point.x*k:.2f} {s.end_point.y*k:.2f}")
            else:
                d.append(f"C{s.c1.x*k:.2f} {s.c1.y*k:.2f} {s.c2.x*k:.2f} {s.c2.y*k:.2f} "
                         f"{s.end_point.x*k:.2f} {s.end_point.y*k:.2f}")
        partes.append("".join(d) + "Z")
    return "".join(partes)


hexa = {n: "#%02X%02X%02X" % c for n, c in CORES.items()}
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w0} {h0}" width="{w0}" height="{h0}">
  <title>JPT Juventude</title>
  <rect id="fundo" width="{w0}" height="{h0}" fill="{hexa['vermelho']}"/>
  <path id="estrela" fill="{hexa['amarelo']}" fill-rule="evenodd" d="{tracar(amarelo)}"/>
  <path id="letras" fill="{hexa['preto']}" fill-rule="evenodd" d="{tracar(preto)}"/>
</svg>
'''
open(SAIDA, "w").write(svg)
print(SAIDA, len(svg), "bytes")
