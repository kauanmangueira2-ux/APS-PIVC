"""Fase 1 — Aquisição: webcam ao vivo e decodificação de imagens recebidas."""
import cv2
import numpy as np


class ErroVisao(Exception):
    """Falha previsível do pipeline; `codigo` é estável para a interface tratar."""

    def __init__(self, codigo: str, mensagem: str, **extra):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.extra = extra          # ex.: segundos restantes do bloqueio


def decodificar(dados: bytes) -> np.ndarray:
    """bytes (JPEG/PNG) -> imagem BGR."""
    img = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ErroVisao("imagem_invalida", "Arquivo de imagem inválido. Envie um JPEG ou PNG.")
    return img


def ler_arquivo(caminho) -> np.ndarray:
    img = cv2.imread(str(caminho))
    if img is None:
        raise ErroVisao("imagem_invalida", f"Não foi possível ler {caminho}.")
    return img


def abrir_webcam(indice=0, largura=1280, altura=720):
    cam = cv2.VideoCapture(indice)
    if not cam.isOpened():
        raise ErroVisao("camera_ausente", "Câmera não encontrada. Conecte uma webcam e tente de novo.")
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
    return cam


if __name__ == "__main__":  # teste de fumaça da Fundação: mostra a webcam
    cam = abrir_webcam()
    while True:
        ok, quadro = cam.read()
        if not ok:
            break
        cv2.imshow("webcam (q para sair)", quadro)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cam.release()
    cv2.destroyAllWindows()
