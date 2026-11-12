"""Métricas: acurácia, FAR, FRR, matriz de confusão e curva ROC (limiar 0,20–0,70).

Estrutura esperada (cadastro e teste SEPARADOS — nunca misture):
  dados/cadastro/<nome>/*.jpg          referência de cada pessoa cadastrada
  testes/conjunto_teste/<nome>/*.jpg   fotos de teste de quem está cadastrado
  testes/conjunto_teste/_desconhecidos/*.jpg   gente que NÃO está cadastrada

Uso:  python -m testes.avaliacao
Saída: docs/figuras/roc.png, docs/figuras/matriz_confusao.png, docs/resultados.csv
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from visao import embedding
from visao.captura import ErroVisao, ler_arquivo

DIR_TESTE = config.BASE_DIR / "testes" / "conjunto_teste"
LIMIARES = np.round(np.arange(0.20, 0.701, 0.05), 2)


def _vetores(pasta):
    saida, tempos = [], []
    for f in sorted(pasta.glob("*.[jp][pn]g")):
        try:
            t = time.perf_counter()
            saida.append(embedding.extrair(ler_arquivo(f)).vetor)
            tempos.append(time.perf_counter() - t)
        except ErroVisao:
            pass  # foto sem rosto utilizável não conta como amostra
    return saida, tempos


def main():
    if not DIR_TESTE.is_dir() or not config.DIR_CADASTRO.is_dir():
        raise SystemExit(
            "Faltam as pastas de imagens. Crie:\n"
            f"  {config.DIR_CADASTRO}/<nome>/*.jpg\n"
            f"  {DIR_TESTE}/<nome>/*.jpg\n"
            f"  {DIR_TESTE}/_desconhecidos/*.jpg"
        )
    galeria = {p.name: _vetores(p)[0] for p in config.DIR_CADASTRO.iterdir() if p.is_dir()}
    nomes = [n for n, v in galeria.items() if v]
    if not nomes:
        raise SystemExit("Nenhuma foto de cadastro utilizável em dados/cadastro/<nome>/.")
    ids = np.array([n for n in nomes for _ in galeria[n]])
    matriz = np.stack([v for n in nomes for v in galeria[n]])

    amostras, tempos = [], []  # (verdadeiro | None, melhor_nome, melhor_score)
    for pasta in DIR_TESTE.iterdir():
        if not pasta.is_dir():
            continue
        verdadeiro = None if pasta.name == "_desconhecidos" else pasta.name
        vetores, t = _vetores(pasta)
        tempos += t
        for v in vetores:
            s = matriz @ v
            i = int(np.argmax(s))
            amostras.append((verdadeiro, ids[i], float(s[i])))
    if not amostras:
        raise SystemExit("Conjunto de teste vazio.")

    linhas = []
    for lim in LIMIARES:
        cad = [a for a in amostras if a[0] is not None]
        desc = [a for a in amostras if a[0] is None]
        aceitos_errados = sum(1 for a in desc if a[2] >= lim)
        far = aceitos_errados / len(desc) if desc else float("nan")
        rejeitados = sum(1 for a in cad if a[2] < lim or a[1] != a[0])
        frr = rejeitados / len(cad) if cad else float("nan")
        certas = sum(1 for a in amostras
                     if (a[0] is None and a[2] < lim) or (a[0] is not None and a[2] >= lim and a[1] == a[0]))
        linhas.append({"limiar": lim, "acuracia": certas / len(amostras), "FAR": far, "FRR": frr})
    df = pd.DataFrame(linhas)
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.BASE_DIR / "docs" / "resultados.csv", index=False)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df["limiar"], df["FAR"], label="FAR (falsa aceitação)")
    ax.plot(df["limiar"], df["FRR"], label="FRR (falsa rejeição)")
    ax.axvline(config.LIMIAR, ls="--", c="gray", label=f"limiar atual {config.LIMIAR}")
    ax.set_xlabel("limiar de similaridade"); ax.set_ylabel("taxa"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(config.DIR_FIGURAS / "roc.png", dpi=150)

    # matriz de confusão no limiar configurado
    rotulos = nomes + ["desconhecido"]
    mc = np.zeros((len(rotulos), len(rotulos)), dtype=int)
    for real, previsto, score in amostras:
        r = rotulos.index(real) if real else len(nomes)
        p = rotulos.index(previsto) if score >= config.LIMIAR else len(nomes)
        mc[r, p] += 1
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(mc, cmap="Blues")
    ax.set_xticks(range(len(rotulos)), rotulos, rotation=45, ha="right"); ax.set_yticks(range(len(rotulos)), rotulos)
    for (i, j), v in np.ndenumerate(mc):
        ax.text(j, i, v, ha="center", va="center")
    ax.set_xlabel("previsto"); ax.set_ylabel("real")
    fig.tight_layout(); fig.savefig(config.DIR_FIGURAS / "matriz_confusao.png", dpi=150)

    print(df.round(3).to_string(index=False))
    print(f"\n{len(amostras)} imagens de teste · {np.mean(tempos) * 1000:.0f} ms por reconhecimento (CPU)")


if __name__ == "__main__":
    main()
