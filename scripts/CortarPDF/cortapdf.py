#!/usr/bin/env python3
"""
cortar_pdf.py — corta páginas de um ou vários PDFs e junta tudo num PDF só,
com uma página opcional de "levantamento" no final.

USO RÁPIDO (um PDF):
    python cortar_pdf.py aula3.pdf --paginas "4-7,12,15-16" -o questoes_aula3.pdf

USO COM PLANO (vários PDFs — é o modo que o agente vai usar):
    python cortar_pdf.py --plano plano.json -o estudo_estatistica.pdf

    plano.json:
    {
      "itens": [
        {"arquivo": "aula1.pdf", "paginas": "3-5,9", "rotulo": "Aula 1 – IC normal"},
        {"arquivo": "livro.pdf", "paginas": "212-215", "offset": 18,
         "rotulo": "Livro – cap. 8 exercícios"}
      ],
      "levantamento": "levantamento.md"
    }

CONVENÇÕES:
- Páginas são 1-based (página 1 = primeira página do arquivo).
- "offset": use quando o número IMPRESSO no livro difere da posição no PDF.
  Página física = página impressa + offset. Ex.: impressa 212 está na posição
  230 do PDF  ->  offset 18.
- Intervalos aceitam "3-7", "12", "20-" (até o fim). Repetições e ordem são
  preservadas como você escreveu.
- Cada item vira um marcador (bookmark) no PDF final, com o rótulo.
- "levantamento" é um .md/.txt que vira página(s) de texto no final do PDF.
"""

import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def parse_paginas(spec: str, total: int, offset: int = 0) -> list[int]:
    """Converte '3-5,9,20-' em índices 0-based, aplicando offset."""
    indices = []
    for parte in str(spec).replace(" ", "").split(","):
        if not parte:
            continue
        if "-" in parte:
            ini, fim = parte.split("-", 1)
            ini = int(ini) + offset
            fim = (int(fim) + offset) if fim else total
        else:
            ini = fim = int(parte) + offset
        if ini < 1 or fim > total or ini > fim:
            raise ValueError(
                f"Intervalo '{parte}' (offset {offset}) fora do PDF, que tem {total} páginas."
            )
        indices.extend(range(ini - 1, fim))
    return indices


def gerar_pagina_texto(texto: str, destino: Path) -> Path:
    """Renderiza um texto/markdown simples em PDF A4 (para o levantamento)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    estilos = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(destino), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    elementos = []
    for linha in texto.splitlines():
        s = linha.rstrip()
        if not s:
            elementos.append(Spacer(1, 6))
            continue
        if s.startswith("# "):
            estilo, s = estilos["Title"], s[2:]
        elif s.startswith("## "):
            estilo, s = estilos["Heading2"], s[3:]
        elif s.startswith("### "):
            estilo, s = estilos["Heading3"], s[4:]
        elif s.lstrip().startswith(("- ", "* ")):
            estilo, s = estilos["BodyText"], "• " + s.lstrip()[2:]
        else:
            estilo = estilos["BodyText"]
        # negrito markdown **x** -> <b>x</b>
        seguro = escape(s)
        partes = seguro.split("**")
        seguro = "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(partes))
        elementos.append(Paragraph(seguro, estilo))
    doc.build(elementos)
    return destino


def montar(itens: list[dict], saida: Path, levantamento: Path | None = None,
           base: Path = Path(".")) -> None:
    writer = PdfWriter()
    resumo = []

    for item in itens:
        caminho = Path(item["arquivo"])
        if not caminho.is_absolute():
            caminho = base / caminho
        reader = PdfReader(str(caminho))
        total = len(reader.pages)
        indices = parse_paginas(item["paginas"], total, int(item.get("offset", 0)))

        inicio = len(writer.pages)
        for i in indices:
            writer.add_page(reader.pages[i])
        rotulo = item.get("rotulo") or f"{caminho.name} p. {item['paginas']}"
        writer.add_outline_item(rotulo, inicio)
        resumo.append(f"{rotulo}: {len(indices)} pág.")

    if levantamento:
        caminho = levantamento if levantamento.is_absolute() else base / levantamento
        tmp = saida.with_suffix(".levantamento.tmp.pdf")
        gerar_pagina_texto(caminho.read_text(encoding="utf-8"), tmp)
        inicio = len(writer.pages)
        for p in PdfReader(str(tmp)).pages:
            writer.add_page(p)
        writer.add_outline_item("Levantamento de questões", inicio)
        tmp.unlink(missing_ok=True)
        resumo.append("Levantamento anexado no final.")

    with open(saida, "wb") as f:
        writer.write(f)

    print(f"OK -> {saida} ({len(writer.pages)} páginas)")
    for linha in resumo:
        print("  -", linha)


def main() -> None:
    ap = argparse.ArgumentParser(description="Corta e junta páginas de PDFs.")
    ap.add_argument("pdf", nargs="?", help="PDF de entrada (modo rápido)")
    ap.add_argument("--paginas", help='Ex.: "3-5,9,20-"')
    ap.add_argument("--offset", type=int, default=0,
                    help="Página física = impressa + offset")
    ap.add_argument("--plano", help="JSON com vários itens (modo agente)")
    ap.add_argument("--levantamento", help=".md/.txt anexado como página final")
    ap.add_argument("-o", "--saida", required=True, help="PDF de saída")
    a = ap.parse_args()

    saida = Path(a.saida)
    try:
        if a.plano:
            plano_path = Path(a.plano)
            plano = json.loads(plano_path.read_text(encoding="utf-8"))
            lev = a.levantamento or plano.get("levantamento")
            montar(plano["itens"], saida, Path(lev) if lev else None,
                   base=plano_path.parent)
        elif a.pdf and a.paginas:
            item = {"arquivo": a.pdf, "paginas": a.paginas, "offset": a.offset}
            montar([item], saida, Path(a.levantamento) if a.levantamento else None)
        else:
            ap.error("Use 'arquivo.pdf --paginas ...' ou '--plano plano.json'.")
    except (ValueError, FileNotFoundError, KeyError) as e:
        sys.exit(f"Erro: {e}")


if __name__ == "__main__":
    main()