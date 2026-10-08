"""Gera o fundo vermelho de papel amassado (estilo cartaz) usado na capa e nos títulos.

uso: python3 textura.py [saida.jpg]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

VERMELHO = (157, 22, 9)


def _ruido(w, h, escala, rng):
    """Ruído suave: campo aleatório pequeno ampliado com interpolação bicúbica."""
    pw, ph = max(2, w // escala), max(2, h // escala)
    base = rng.random((ph, pw)).astype(np.float32)
    img = Image.fromarray((base * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255 - 0.5


def _vincos(w, h, n, rng):
    """Vincos de papel: linhas finas com um lado claro e outro escuro."""
    luz = Image.new("L", (w, h), 128)
    from PIL import ImageDraw
    d = ImageDraw.Draw(luz)
    for _ in range(n):
        x0, y0 = rng.random() * w, rng.random() * h
        ang = rng.random() * np.pi
        comp = (0.25 + rng.random() * 0.9) * max(w, h)
        dx, dy = np.cos(ang) * comp / 2, np.sin(ang) * comp / 2
        a, b = (x0 - dx, y0 - dy), (x0 + dx, y0 + dy)
        nx, ny = -np.sin(ang) * 2, np.cos(ang) * 2
        forca = int(10 + rng.random() * 22)
        d.line([a, b], fill=128 + forca, width=2)
        d.line([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)], fill=128 - forca, width=3)
    luz = luz.filter(ImageFilter.GaussianBlur(1.6))
    return np.asarray(luz, dtype=np.float32) / 255 - 0.5


def gerar(caminho, w=1240, h=1754, semente=13):
    rng = np.random.default_rng(semente)
    campo = (_ruido(w, h, 260, rng) * 0.30 + _ruido(w, h, 70, rng) * 0.14
             + _ruido(w, h, 16, rng) * 0.06)
    campo += _vincos(w, h, 34, rng) * 2.6
    grao = rng.normal(0, 0.035, (h, w)).astype(np.float32)
    # luz vinda do canto superior esquerdo, como no cartaz
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    luz = 0.06 * (1 - (xx / w * 0.6 + yy / h * 0.4))
    fator = 1 + campo * 0.38 + grao + luz
    rgb = np.stack([np.clip(c * fator, 0, 255) for c in VERMELHO], axis=-1).astype(np.uint8)
    Image.fromarray(rgb).save(caminho, quality=82, optimize=True)
    return caminho


PAPEL = (247, 241, 230)


def _ruido_periodico(w, h, sigma, rng):
    """Ruído suave que emenda nas bordas (filtro gaussiano no domínio da frequência)."""
    branco = rng.normal(0, 1, (h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    filtro = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    campo = np.real(np.fft.ifft2(np.fft.fft2(branco) * filtro))
    return (campo / (np.abs(campo).max() or 1) * 0.5).astype(np.float32)


def _vincos_periodicos(w, h, n, rng):
    """Vincos desenhados numa tela 3x3 e dobrados, para o ladrilho emendar sem costura."""
    from PIL import ImageDraw
    W, H = w * 3, h * 3
    tela = Image.new("L", (W, H), 128)
    d = ImageDraw.Draw(tela)
    for _ in range(n):
        x0, y0 = w + rng.random() * w, h + rng.random() * h
        ang = rng.random() * np.pi
        comp = (0.3 + rng.random() * 0.9) * max(w, h)
        dx, dy = np.cos(ang) * comp / 2, np.sin(ang) * comp / 2
        nx, ny = -np.sin(ang) * 2.5, np.cos(ang) * 2.5
        forca = int(6 + rng.random() * 14)
        d.line([(x0 - dx, y0 - dy), (x0 + dx, y0 + dy)], fill=128 + forca, width=3)
        d.line([(x0 - dx + nx, y0 - dy + ny), (x0 + dx + nx, y0 + dy + ny)], fill=128 - forca, width=4)
    t = np.asarray(tela.filter(ImageFilter.GaussianBlur(2.2)), dtype=np.float32) / 255 - 0.5
    return sum(t[j * h:(j + 1) * h, i * w:(i + 1) * w] for i in range(3) for j in range(3))


def gerar_papel(caminho, w=1240, h=1754, semente=7):
    """Papel creme levemente amassado para as páginas internas (ladrilho sem costura)."""
    rng = np.random.default_rng(semente)
    campo = _ruido_periodico(w, h, 90, rng) * 0.9 + _ruido_periodico(w, h, 22, rng) * 0.35
    campo += _vincos_periodicos(w, h, 26, rng) * 4.0
    grao = rng.normal(0, 0.012, (h, w)).astype(np.float32)
    fator = 1 + campo * 0.07 + grao
    rgb = np.stack([np.clip(c * fator, 0, 255) for c in PAPEL], axis=-1).astype(np.uint8)
    Image.fromarray(rgb).save(caminho, quality=80, optimize=True)
    return caminho


if __name__ == "__main__":
    gerar(sys.argv[1] if len(sys.argv) > 1 else "templates/textura-vermelha.jpg")
    gerar_papel(sys.argv[2] if len(sys.argv) > 2 else "templates/textura-papel.jpg")
