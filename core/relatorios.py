"""Exportação do log de auditoria em CSV e PDF."""
import csv
import io

COLUNAS = ["ocorrido_em", "usuario", "recurso", "resultado", "score"]
TITULOS = ["Data/hora", "Pessoa", "Recurso", "Resultado", "Score"]

ROTULOS = {
    "concedido": "Concedido",
    "negado_nivel": "Negado · nível",
    "negado_divisao": "Negado · divisão",
    "negado_horario": "Negado · horário",
    "nao_reconhecido": "Não reconhecido",
    "falha_liveness": "Falha na prova de vida",
    "pin_invalido": "PIN inválido",
    "pin_bloqueado": "PIN bloqueado",
}


def _linha(r):
    return [
        str(r["ocorrido_em"]),
        r["usuario"] or "— não reconhecido —",
        r["recurso"] or "—",
        ROTULOS.get(r["resultado"], r["resultado"]),
        f"{r['score']:.3f}" if r["score"] is not None else "",
    ]


def para_csv(registros) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(TITULOS)
    w.writerows(_linha(r) for r in registros)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM para o Excel abrir com acentos


def para_pdf(registros) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Relatório de auditoria")
    estilos = getSampleStyleSheet()
    dados = [TITULOS] + [_linha(r) for r in registros]
    tabela = Table(dados, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]
    for i, r in enumerate(registros, start=1):
        if r["resultado"] != "concedido":
            estilo.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#9B3B33")))
    tabela.setStyle(TableStyle(estilo))
    doc.build([
        Paragraph("Cofre Biométrico — Relatório de auditoria", estilos["Title"]),
        Paragraph(f"{len(registros)} registro(s)", estilos["Normal"]),
        tabela,
    ])
    return buf.getvalue()
