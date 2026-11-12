"""Fases 2–4 encadeadas: do quadro bruto ao vetor de 512 posições (APS-14)."""
from dataclasses import dataclass

import numpy as np

from visao import detector, preproc


@dataclass
class Resultado:
    vetor: np.ndarray      # float32, 512, norma L2 = 1
    bbox: tuple            # x1, y1, x2, y2
    qualidade: float       # det_score do SCRFD


def extrair(bgr: np.ndarray) -> Resultado:
    """Recebe um quadro BGR e devolve o vetor do único rosto. Levanta ErroVisao se não der."""
    preproc.verificar_iluminacao(bgr)
    processada = preproc.preprocessar(bgr)
    rosto = detector.exigir_um_rosto(detector.detectar(processada))
    vetor = np.asarray(rosto.normed_embedding, dtype=np.float32)
    return Resultado(vetor=vetor, bbox=tuple(float(v) for v in rosto.bbox), qualidade=float(rosto.det_score))


def para_bytes(vetor: np.ndarray) -> bytes:
    return np.asarray(vetor, dtype=np.float32).tobytes()


def de_bytes(dados: bytes) -> np.ndarray:
    return np.frombuffer(dados, dtype=np.float32)
