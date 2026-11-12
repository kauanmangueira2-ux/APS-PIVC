"""Galeria biométrica em memória: matriz NumPy carregada do banco."""
import threading

import numpy as np

from db import repositorio
from visao.embedding import de_bytes

_trava = threading.Lock()
_ids = np.empty(0, dtype=np.int64)
_matriz = np.empty((0, 512), dtype=np.float32)


def recarregar():
    """Relê o banco. Chamar após cadastro, edição de status ou remoção."""
    global _ids, _matriz
    linhas = repositorio.carregar_biometrias_ativas()
    with _trava:
        if linhas:
            _ids = np.array([l["usuario_id"] for l in linhas], dtype=np.int64)
            _matriz = np.stack([de_bytes(l["vetor"]) for l in linhas])
        else:
            _ids = np.empty(0, dtype=np.int64)
            _matriz = np.empty((0, 512), dtype=np.float32)


def instantaneo():
    with _trava:
        return _ids, _matriz


def tamanho() -> int:
    return len(instantaneo()[0])
