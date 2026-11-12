"""Valida a prova de vida na SUA webcam: mostra o EAR ao vivo e avisa quando detecta piscada.

Uso:  python -m testes.calibrar_piscada      (q para sair)
Com olhos abertos o EAR fica perto de 0,25–0,35; ao fechar cai para perto de 0,1. Pisque
algumas vezes: deve aparecer PISCOU. Se piscadas reais passarem batido, aumente PISCADA_QUEDA
(ex.: 0,75) em config.py; se aparecer PISCOU com o rosto parado, diminua (ex.: 0,6).
"""
from collections import deque

import cv2

from visao import liveness
from visao.captura import abrir_webcam


def main():
    liveness.preparar()
    cam = abrir_webcam()
    janela = deque(maxlen=15)   # ~3 s no terminal real (15 quadros a cada 0,2 s)
    while True:
        ok, quadro = cam.read()
        if not ok:
            break
        n, ear = liveness.analisar_quadro(quadro)
        if ear is not None:
            janela.append(ear)
        piscadas = liveness.contar_piscadas(list(janela))
        texto = "sem rosto" if ear is None else f"EAR {ear:.3f}  piscadas {piscadas}"
        if n > 1:
            texto += "  (mais de um rosto)"
        cor = (60, 160, 60) if piscadas >= 1 else (210, 210, 210)
        cv2.putText(quadro, texto, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, cor, 2)
        cv2.imshow("validar piscada (q para sair)", quadro)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
