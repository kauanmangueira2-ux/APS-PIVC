"""Fase 5 — Reconhecimento: similaridade do cosseno contra a galeria."""
import numpy as np

import config
from core import galeria


def ranking(vetor: np.ndarray):
    """Melhor score de CADA pessoa (várias fotos por pessoa contam como uma), do maior ao menor.
    Vetores já vêm normalizados em L2, então o cosseno é um produto escalar — a galeria
    inteira em uma multiplicação. Devolve lista de (usuario_id, score)."""
    ids, matriz = galeria.instantaneo()
    if len(ids) == 0:
        return []
    scores = matriz @ vetor
    pessoas, posicao = np.unique(ids, return_inverse=True)
    melhor = np.full(len(pessoas), -1.0, dtype=np.float32)
    np.maximum.at(melhor, posicao, scores)
    ordem = np.argsort(melhor)[::-1]
    return [(int(pessoas[i]), float(melhor[i])) for i in ordem]


def identificar(vetor: np.ndarray, limiar: float = None, margem: float = None):
    """Devolve (usuario_id | None, melhor_score).

    Aceita só se o melhor score passa do limiar E vence a segunda pessoa por uma margem:
    se dois cadastrados empatam, é mais seguro não reconhecer do que abrir para a pessoa errada."""
    limiar = config.LIMIAR if limiar is None else limiar
    margem = config.MARGEM_IDENTIFICACAO if margem is None else margem
    rank = ranking(vetor)
    if not rank:
        return None, 0.0
    uid, melhor = rank[0]
    segundo = rank[1][1] if len(rank) > 1 else -1.0
    if melhor < limiar or (melhor - segundo) < margem:
        return None, melhor
    return uid, melhor


def parecido_com(vetor: np.ndarray, ignorar: int = None, limiar: float = None):
    """Pessoa já cadastrada (diferente de `ignorar`) cujo rosto passa do limiar, ou (None, score)."""
    limiar = config.LIMIAR if limiar is None else limiar
    for uid, score in ranking(vetor):
        if uid == ignorar:
            continue
        return (uid, score) if score >= limiar else (None, score)
    return None, 0.0


def menor_similaridade_entre(vetores: list):
    """(i, j, score) do par de fotos MENOS parecido (índices a partir de 1), ou None se < 2 fotos."""
    if len(vetores) < 2:
        return None
    m = np.stack(vetores) @ np.stack(vetores).T
    np.fill_diagonal(m, 2.0)
    i, j = np.unravel_index(int(np.argmin(m)), m.shape)
    return int(min(i, j)) + 1, int(max(i, j)) + 1, float(m[i, j])
