"""Fase 2 — Pré-processamento: iluminação (CLAHE no canal L) e ruído (filtro bilateral)."""
import cv2
import numpy as np

import config
from visao.captura import ErroVisao


def luminosidade(bgr: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    return float(lab[:, :, 0].mean())


def verificar_iluminacao(bgr: np.ndarray):
    if luminosidade(bgr) < config.LUMINOSIDADE_MIN:
        raise ErroVisao("imagem_escura", "Imagem escura demais. Acenda a luz ou aproxime-se da iluminação.")


def aplicar_clahe(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def reduzir_ruido(bgr: np.ndarray) -> np.ndarray:
    return cv2.bilateralFilter(bgr, d=5, sigmaColor=40, sigmaSpace=40)


def preprocessar(bgr: np.ndarray) -> np.ndarray:
    """Pipeline completo da fase 2. O InsightFace espera BGR, então não convertemos para RGB."""
    return reduzir_ruido(aplicar_clahe(bgr))
