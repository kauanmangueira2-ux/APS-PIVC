"""Gera a figura das fases 1–4 lado a lado para uma foto (dissertação).

Uso:  python docs/gerar_figuras.py caminho/da/foto.jpg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from visao import detector, preproc
from visao.captura import ler_arquivo


def rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def main(caminho):
    original = ler_arquivo(caminho)
    clahe = preproc.aplicar_clahe(original)
    final = preproc.reduzir_ruido(clahe)
    rosto = detector.exigir_um_rosto(detector.detectar(final))

    marcado = final.copy()
    x1, y1, x2, y2 = map(int, rosto.bbox)
    cv2.rectangle(marcado, (x1, y1), (x2, y2), (0, 200, 0), 2)
    for px, py in rosto.kps.astype(int):
        cv2.circle(marcado, (px, py), 3, (0, 0, 255), -1)
    alinhado = detector.recorte_alinhado(final, rosto)

    etapas = [("1 · Aquisição", original), ("2a · CLAHE (canal L)", clahe),
              ("2b · Filtro bilateral", final), ("3a · Caixa + 5 pontos", marcado),
              ("3b · Alinhado 112×112", alinhado)]
    fig, eixos = plt.subplots(1, len(etapas), figsize=(4 * len(etapas), 4))
    for ax, (titulo, img) in zip(eixos, etapas):
        ax.imshow(rgb(img)); ax.set_title(titulo, fontsize=10); ax.axis("off")
    fig.tight_layout()
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    saida = config.DIR_FIGURAS / f"fases_{Path(caminho).stem}.png"
    fig.savefig(saida, dpi=150)
    print(f"Figura salva em {saida} · vetor de 512 posições na fase 4 (ver visao/embedding.py)")


if __name__ == "__main__":
    main(sys.argv[1])
