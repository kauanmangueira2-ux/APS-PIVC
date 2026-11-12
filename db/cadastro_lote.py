"""Cadastra biometrias a partir de dados/cadastro/<matricula>/*.jpg.

Uso:  python -m db.cadastro_lote
A pessoa precisa existir (ex.: dados de demonstração de `python -m db.init_db`).
"""
import config
from db import repositorio
from db.conexao import cursor
from visao import embedding
from visao.captura import ErroVisao, ler_arquivo


def main():
    for pasta in sorted(p for p in config.DIR_CADASTRO.iterdir() if p.is_dir()):
        with cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE matricula=%s", (pasta.name,))
            u = cur.fetchone()
        if not u:
            print(f"[pulado] matrícula {pasta.name} não existe no banco")
            continue
        repositorio.limpar_biometrias(u["id"])
        ok = 0
        for foto in sorted(pasta.glob("*.[jp][pn]g")):
            try:
                r = embedding.extrair(ler_arquivo(foto))
                repositorio.adicionar_biometria(u["id"], embedding.para_bytes(r.vetor), r.qualidade)
                ok += 1
            except ErroVisao as e:
                print(f"  {foto.name}: {e.mensagem}")
        print(f"{pasta.name}: {ok} biometrias gravadas")


if __name__ == "__main__":
    main()
