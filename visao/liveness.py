"""Prova de vida por piscada: EAR (Eye Aspect Ratio) com o MediaPipe FaceMesh.

Fica na API clássica `mp.solutions` (mediapipe 0.10.14, Python 3.11/3.12), que já vem com o
modelo — nada para baixar.
"""
import threading

import cv2
import numpy as np

import config

# índices do FaceMesh: p1, p2, p3, p4, p5, p6 de cada olho
_OLHO_DIR = (33, 160, 158, 133, 153, 144)
_OLHO_ESQ = (362, 385, 387, 263, 373, 380)

_mesh = None
_trava = threading.Lock()   # o FaceMesh não é thread-safe e a API atende em várias threads


def _facemesh():
    global _mesh
    if _mesh is None:
        import mediapipe as mp
        if not hasattr(mp, "solutions"):
            raise RuntimeError(
                f"mediapipe {getattr(mp, '__version__', '?')} não tem a API 'solutions'. "
                "Use Python 3.11 e instale a versão fixada: pip install -r requirements.txt"
            )
        _mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=2, refine_landmarks=True
        )
    return _mesh


def preparar():
    """Carrega o FaceMesh. Chamado em segundo plano na inicialização da API."""
    with _trava:
        _facemesh()


def disponivel() -> bool:
    """True se a prova de vida está pronta (usado em /api/saude)."""
    return _mesh is not None


def _ear(pts, idx):
    p = [pts[i] for i in idx]
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horizontal = 2.0 * np.linalg.norm(p[0] - p[3])
    return vertical / horizontal if horizontal else 0.0


def analisar_quadro(bgr: np.ndarray):
    """(quantidade de rostos, EAR médio dos dois olhos do rosto principal ou None)."""
    h, w = bgr.shape[:2]
    with _trava:
        res = _facemesh().process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    rostos = res.multi_face_landmarks or []
    if not rostos:
        return 0, None
    pts = np.array([[l.x * w, l.y * h] for l in rostos[0].landmark])
    return len(rostos), float((_ear(pts, _OLHO_DIR) + _ear(pts, _OLHO_ESQ)) / 2.0)


def ear_do_quadro(bgr: np.ndarray):
    """EAR médio dos dois olhos, ou None se o FaceMesh não achar rosto."""
    return analisar_quadro(bgr)[1]


def contar_piscadas(ears: list) -> int:
    """Quantas vezes os olhos foram de abertos -> fechados -> abertos na sequência.

    Os limiares são relativos à mediana da própria rajada, então funcionam para olhos
    maiores ou menores. Só conta a partir do primeiro quadro com olhos abertos."""
    if len(ears) < config.PISCADA_MIN_QUADROS:
        return 0
    base = float(np.median(ears))
    if base < config.EAR_ABERTO_MIN:
        return 0
    fechado, aberto = config.PISCADA_QUEDA * base, config.PISCADA_REABERTURA * base
    estado, piscadas = None, 0
    for e in ears:
        if e >= aberto:
            if estado == "fechado":
                piscadas += 1
            estado = "aberto"
        elif e <= fechado and estado == "aberto":
            estado = "fechado"
    return piscadas


def detectou_piscada(ears: list) -> bool:
    return contar_piscadas(ears) >= config.PISCADAS_EXIGIDAS


def piscou(quadros: list) -> bool:
    """True se, na rajada, uma única pessoa piscou o número de vezes exigido.
    Se aparecer mais de um rosto em qualquer quadro (ex.: alguém segurando uma foto), reprova."""
    ears = []
    for q in quadros:
        n, ear = analisar_quadro(q)
        if n > 1:
            return False
        if ear is not None:
            ears.append(ear)
    return detectou_piscada(ears)
