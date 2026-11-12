#!/usr/bin/env python3
"""
montar.py — monta o PDF final do Monitor em três blocos.

  Bloco 1  resumo.md            (teoria, 4–5 páginas)
  Bloco 2  levantamento.md      (incidência + direcionamento; {{pg:ID}} vira página)
  Bloco 3  questões recortadas  (páginas originais, carimbadas com o ID)

O corte simples de páginas continua no CortarPDF/cortapdf.py; este script é só
para a montagem do material.

Uso:
    python montar.py --plano plano.json -o "Estudo P2.pdf"

plano.json
{
  "titulo": "Cálculo — P2",
  "resumo": "resumo.md",
  "levantamento": "levantamento.md",
  "carimbo": true,
  "questoes": [
    {"id": "A6-E8", "grupo": "Aulas", "arquivo": "../../Materiais Base/aula6.pdf",
     "paginas": "93,99", "rotulo": "Aula 6 — ex. 6"},
    {"id": "L-C12P14", "grupo": "Livro", "arquivo": "../../Materiais Base/livro_313_465.pdf",
     "paginas": "47"}
  ]
}

  - Caminhos relativos são relativos à pasta do plano.json.
  - {{pg:A6-E8}} no levantamento vira o número da página DESTE PDF onde a
    questão começa (o script calcula em duas passadas).
  - Cada mudança de "grupo" abre uma página divisória.
  - "offset" opcional por questão: página do arquivo = informada + offset.
  - Markdown aceito: # ## ###, listas, **negrito**, *itálico*, tabelas com |,
    x_{sub}, x^{sup} e a linha <!-- quebra --> para nova página.
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter

# --------------------------------------------------------------------------- páginas


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


# --------------------------------------------------------------------------- fontes

_FONTE = None


def fonte() -> tuple[str, str]:
    """Registra uma fonte com acentos e letras gregas (σ, μ, √...)."""
    global _FONTE
    if _FONTE:
        return _FONTE
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidatos = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "C:/Windows/Fonts/ariali.ttf", "C:/Windows/Fonts/arialbi.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/Library/Fonts/Arial Italic.ttf", "/Library/Fonts/Arial Bold Italic.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
    ]
    for reg, bold, ital, bi in candidatos:
        if all(Path(p).exists() for p in (reg, bold, ital, bi)):
            for nome, arq in (("Uni", reg), ("Uni-B", bold), ("Uni-I", ital), ("Uni-BI", bi)):
                pdfmetrics.registerFont(TTFont(nome, arq))
            addMapping("Uni", 0, 0, "Uni")
            addMapping("Uni", 1, 0, "Uni-B")
            addMapping("Uni", 0, 1, "Uni-I")
            addMapping("Uni", 1, 1, "Uni-BI")
            _FONTE = ("Uni", "Uni-B")
            return _FONTE
    print("Aviso: nenhuma fonte Unicode encontrada; letras gregas podem sair como quadrados.")
    _FONTE = ("Helvetica", "Helvetica-Bold")
    return _FONTE


def estilos():
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle

    reg, bold = fonte()
    tinta, destaque = HexColor("#1f2933"), HexColor("#7a5aa6")
    return {
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=17, leading=21, spaceAfter=8,
                             textColor=destaque),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=16, spaceBefore=8,
                             spaceAfter=4, textColor=tinta),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=10.5, leading=13.5, spaceBefore=5,
                             spaceAfter=2, textColor=tinta),
        "p": ParagraphStyle("p", fontName=reg, fontSize=9.5, leading=12.8, spaceAfter=3,
                            textColor=tinta),
        "li": ParagraphStyle("li", fontName=reg, fontSize=9.5, leading=12.6, leftIndent=12,
                             bulletIndent=2, spaceAfter=1.5, textColor=tinta),
        "cel": ParagraphStyle("cel", fontName=reg, fontSize=8.2, leading=10.2, textColor=tinta),
        "celh": ParagraphStyle("celh", fontName=bold, fontSize=8.2, leading=10.2, textColor=tinta),
        "div": ParagraphStyle("div", fontName=bold, fontSize=26, leading=32, alignment=1,
                              textColor=destaque),
        "divsub": ParagraphStyle("divsub", fontName=reg, fontSize=11, leading=15, alignment=1,
                                 textColor=tinta),
    }


# --------------------------------------------------------------------------- markdown -> PDF


def inline(s: str) -> str:
    from xml.sax.saxutils import escape

    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    s = re.sub(r"_\{(.+?)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"\^\{(.+?)\}", r"<super>\1</super>", s)
    return s


def md_para_pdf(texto: str, destino: Path) -> int:
    """Renderiza markdown simples em A4. Retorna o número de páginas."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    st = estilos()
    largura = A4[0] - 3.6 * cm
    el, tabela = [], []

    def fecha_tabela():
        if not tabela:
            return
        linhas = [l for l in tabela if not re.fullmatch(r"\|?[\s:\-|]+\|?", l)]
        celulas = [[c.strip() for c in l.strip().strip("|").split("|")] for l in linhas]
        ncol = max(len(c) for c in celulas)
        dados = [[Paragraph(inline(c[i]) if i < len(c) else "", st["celh" if r == 0 else "cel"])
                  for i in range(ncol)] for r, c in enumerate(celulas)]
        # largura das colunas proporcional ao texto (com piso)
        pesos = [max(4, max(len(c[i]) if i < len(c) else 0 for c in celulas)) for i in range(ncol)]
        pesos = [min(p, 60) for p in pesos]
        tot = sum(pesos)
        t = Table(dados, colWidths=[largura * p / tot for p in pesos], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#efe8f6")),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#c9bfd8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        el.extend([t, Spacer(1, 6)])
        tabela.clear()

    for bruta in texto.splitlines():
        s = bruta.rstrip()
        if s.lstrip().startswith("|"):
            tabela.append(s)
            continue
        fecha_tabela()
        if not s.strip():
            el.append(Spacer(1, 4))
        elif s.strip() == "<!-- quebra -->":
            el.append(PageBreak())
        elif s.startswith("# "):
            el.append(Paragraph(inline(s[2:]), st["h1"]))
        elif s.startswith("## "):
            el.append(Paragraph(inline(s[3:]), st["h2"]))
        elif s.startswith("### "):
            el.append(KeepTogether([Paragraph(inline(s[4:]), st["h3"])]))
        elif re.match(r"\s*([-*]|\d+\.)\s", s):
            m = re.match(r"(\s*)([-*]|\d+\.)\s+(.*)", s)
            nivel = len(m.group(1)) // 2
            marca = "•" if m.group(2) in "-*" else m.group(2)
            estilo = st["li"].clone("li%d" % nivel, leftIndent=12 + 12 * nivel,
                                    bulletIndent=2 + 12 * nivel)
            el.append(Paragraph(inline(m.group(3)), estilo, bulletText=marca))
        else:
            el.append(Paragraph(inline(s), st["p"]))
    fecha_tabela()

    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    doc.build(el or [Spacer(1, 1)])
    return len(PdfReader(str(destino)).pages)


def pagina_divisoria(titulo: str, subtitulo: str, destino: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    st = estilos()
    doc = SimpleDocTemplate(str(destino), pagesize=A4)
    doc.build([Spacer(1, A4[1] / 3), Paragraph(inline(titulo), st["div"]), Spacer(1, 10),
               Paragraph(inline(subtitulo), st["divsub"])])


def carimbo(texto: str, largura: float, altura: float, x0: float = 0.0, y0: float = 0.0):
    """Página transparente com o código da questão no canto superior direito.

    largura/altura e (x0, y0) descrevem a área VISÍVEL (cropbox) da página de destino,
    para que o carimbo não caia fora do recorte em PDFs com cropbox < mediabox.
    """
    from reportlab.lib.colors import HexColor, white
    from reportlab.pdfgen import canvas

    reg, bold = fonte()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(x0 + largura, y0 + altura))
    tam = max(7, min(11, largura / 60))
    w = c.stringWidth(texto, bold, tam) + 10
    x, y = x0 + largura - w - 8, y0 + altura - tam - 12
    c.setFillColor(white)
    c.setStrokeColor(HexColor("#7a5aa6"))
    c.roundRect(x, y, w, tam + 7, 3, fill=1, stroke=1)
    c.setFillColor(HexColor("#7a5aa6"))
    c.setFont(bold, tam)
    c.drawString(x + 5, y + 4, texto)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


# --------------------------------------------------------------------------- montagem


def resolver(caminho: str, base: Path) -> Path:
    p = Path(caminho)
    return p if p.is_absolute() else (base / p).resolve()


def montar_material(plano: dict, base: Path, saida: Path) -> None:
    tmp = saida.parent / f".{saida.stem}.tmp"
    tmp.mkdir(exist_ok=True)
    try:
        _montar(plano, base, saida, tmp)
    finally:
        for f in tmp.glob("*"):
            f.unlink()
        tmp.rmdir()


def _montar(plano: dict, base: Path, saida: Path, tmp: Path) -> None:
    questoes = plano.get("questoes", [])
    leitores, avisos = {}, []

    # 1) resolve as páginas de cada questão (falha cedo se algo estiver errado)
    for q in questoes:
        arq = resolver(q["arquivo"], base)
        if arq not in leitores:
            if not arq.exists():
                raise FileNotFoundError(f"{q.get('id')}: não achei {arq}")
            leitores[arq] = PdfReader(str(arq))
        q["_arq"] = arq
        q["_idx"] = parse_paginas(q["paginas"], len(leitores[arq].pages), int(q.get("offset", 0)))

    # 2) resumo (Bloco 1)
    resumo_pdf = None
    if plano.get("resumo"):
        resumo_pdf = tmp / "resumo.pdf"
        md_para_pdf(resolver(plano["resumo"], base).read_text(encoding="utf-8"), resumo_pdf)
    n_resumo = len(PdfReader(str(resumo_pdf)).pages) if resumo_pdf else 0

    # 3) levantamento (Bloco 2) em duas passadas para acertar {{pg:ID}}
    lev_texto = resolver(plano["levantamento"], base).read_text(encoding="utf-8") \
        if plano.get("levantamento") else ""
    ids = {q.get("id") for q in questoes}
    for ref in sorted(set(re.findall(r"\{\{pg:([^}]+)\}\}", lev_texto)) - ids):
        avisos.append(f"o levantamento cita {ref}, que não está em 'questoes'")

    def posicoes(n_lev: int) -> dict:
        pos, pag, grupo = {}, n_resumo + n_lev + 1, None
        for q in questoes:
            if q.get("grupo") != grupo:
                grupo = q.get("grupo")
                if grupo:
                    pag += 1  # página divisória
            pos.setdefault(q.get("id"), pag)
            pag += len(q["_idx"])
        return pos

    lev_pdf, n_lev = None, 0
    if lev_texto:
        lev_pdf = tmp / "levantamento.pdf"
        for _ in range(3):
            pos = posicoes(n_lev)
            texto = re.sub(r"\{\{pg:([^}]+)\}\}", lambda m: str(pos.get(m.group(1), "?")), lev_texto)
            novo = md_para_pdf(texto, lev_pdf)
            if novo == n_lev:
                break
            n_lev = novo
    pos = posicoes(n_lev)

    # 4) junta tudo
    w = PdfWriter()
    titulo = plano.get("titulo", "Material de estudo")
    if resumo_pdf:
        w.add_outline_item("Bloco 1 — Resumo", len(w.pages))
        for p in PdfReader(str(resumo_pdf)).pages:
            w.add_page(p)
    if lev_pdf:
        w.add_outline_item("Bloco 2 — Levantamento", len(w.pages))
        for p in PdfReader(str(lev_pdf)).pages:
            w.add_page(p)

    marcador_b3, marcador_grupo, grupo = None, None, None
    usar_carimbo = plano.get("carimbo", True)
    for k, q in enumerate(questoes):
        if marcador_b3 is None:
            marcador_b3 = w.add_outline_item("Bloco 3 — Questões", len(w.pages))
        if q.get("grupo") != grupo:
            grupo = q.get("grupo")
            if grupo:
                div = tmp / f"div{k}.pdf"
                n_grupo = sum(1 for x in questoes if x.get("grupo") == grupo)
                pagina_divisoria(grupo, f"{titulo} · {n_grupo} questão(ões)", div)
                marcador_grupo = w.add_outline_item(grupo, len(w.pages), parent=marcador_b3)
                w.add_page(PdfReader(str(div)).pages[0])
        inicio = len(w.pages)
        leitor = leitores[q["_arq"]]
        for i in q["_idx"]:
            src = leitor.pages[i]
            if usar_carimbo and q.get("id"):
                # cópia própria da página: se duas questões usam a mesma página,
                # cada cópia recebe só o seu código
                novo = PageObject.create_blank_page(width=float(src.mediabox.right),
                                                    height=float(src.mediabox.top))
                novo.merge_page(src)
                novo.mediabox = src.mediabox
                novo.cropbox = src.cropbox
                if src.get("/Rotate"):
                    novo.rotation = src.rotation
                cb = src.cropbox
                novo.merge_page(carimbo(q["id"], float(cb.width), float(cb.height),
                                        float(cb.left), float(cb.bottom)))
                w.add_page(novo)
            else:
                w.add_page(src)
        rotulo = q.get("rotulo") or q.get("id") or f"{q['_arq'].name} p.{q['paginas']}"
        w.add_outline_item(f"{q.get('id', '')}  {rotulo}".strip() if q.get("rotulo") else rotulo,
                           inicio, parent=marcador_grupo or marcador_b3)
        if q.get("id") in pos and pos[q["id"]] != inicio + 1 and k == next(
                j for j, x in enumerate(questoes) if x.get("id") == q.get("id")):
            avisos.append(f"página calculada de {q['id']} não bateu ({pos[q['id']]} vs {inicio + 1})")

    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "wb") as f:
        w.write(f)

    print(f"OK -> {saida} ({len(w.pages)} páginas)")
    print(f"  Bloco 1 resumo: {n_resumo} pág. | Bloco 2 levantamento: {n_lev} pág. | "
          f"Bloco 3: {len(questoes)} questão(ões)")
    for a in avisos:
        print("  AVISO:", a)


def main() -> None:
    ap = argparse.ArgumentParser(description="Monta o PDF final (resumo + levantamento + questões).")
    ap.add_argument("--plano", required=True, help="plano.json")
    ap.add_argument("-o", "--saida", required=True, help="PDF de saída")
    a = ap.parse_args()

    try:
        plano_path = Path(a.plano).resolve()
        plano = json.loads(plano_path.read_text(encoding="utf-8"))
        montar_material(plano, plano_path.parent, Path(a.saida).resolve())
    except (ValueError, FileNotFoundError, KeyError) as e:
        sys.exit(f"Erro: {e}")


if __name__ == "__main__":
    main()
