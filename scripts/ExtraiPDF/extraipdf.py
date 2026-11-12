"""
Extrai o texto de PDFs para arquivos .md, em paralelo.

Instalação:
    pip install pymupdf

Uso:
    python extrair_texto_pdf.py "C:/caminho/arquivo.pdf"
    python extrair_texto_pdf.py "C:/caminho/pasta"
    python extrair_texto_pdf.py "C:/caminho/pasta" --refazer   (reconverte mesmo se o .md já existir)

O .md é salvo ao lado de cada PDF, com o mesmo nome.
"""

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # PyMuPDF


def processar(caminho: str) -> tuple[str, int, int, float, str]:
    """Converte um PDF. Roda em processo separado. Retorna (nome, páginas, caracteres, segundos, erro)."""
    inicio = time.perf_counter()
    pdf = Path(caminho)
    saida = pdf.with_suffix(".md")
    total_chars = 0
    try:
        with fitz.open(pdf) as doc, open(saida, "w", encoding="utf-8") as f:
            n_paginas = doc.page_count
            f.write(f"# {pdf.stem}\n\n")
            for i in range(n_paginas):
                # sort=False é mais rápido; o texto sai na ordem em que está gravado no PDF
                texto = doc[i].get_text("text", sort=False).strip()
                total_chars += len(texto)
                f.write(f"## Página {i + 1}\n\n{texto}\n\n")
        return pdf.name, n_paginas, total_chars, time.perf_counter() - inicio, ""
    except Exception as e:
        return pdf.name, 0, 0, time.perf_counter() - inicio, str(e)


def precisa_converter(pdf: Path, refazer: bool) -> bool:
    md = pdf.with_suffix(".md")
    if refazer or not md.exists():
        return True
    return md.stat().st_mtime < pdf.stat().st_mtime  # PDF mudou depois do .md


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refazer = "--refazer" in sys.argv
    if not args:
        print('Uso: python extrair_texto_pdf.py "caminho/arquivo.pdf" ou "caminho/pasta" [--refazer]')
        sys.exit(1)

    alvo = Path(args[0])
    if not alvo.exists():
        print(f"Não encontrei: {alvo}")
        sys.exit(1)

    pdfs = sorted(alvo.glob("*.pdf")) if alvo.is_dir() else [alvo]
    pendentes = [p for p in pdfs if precisa_converter(p, refazer)]
    pulados = len(pdfs) - len(pendentes)
    if pulados:
        print(f"Pulando {pulados} PDF(s) já convertido(s). Use --refazer para forçar.")
    if not pendentes:
        print("Nada a fazer.")
        return

    # Os maiores primeiro, para não ficar um PDF gigante sozinho no final
    pendentes.sort(key=lambda p: p.stat().st_size, reverse=True)
    workers = min(len(pendentes), os.cpu_count() or 4)
    print(f"Convertendo {len(pendentes)} PDF(s) com {workers} processo(s)...\n")

    inicio = time.perf_counter()
    feitos = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futuros = [pool.submit(processar, str(p)) for p in pendentes]
        for fut in as_completed(futuros):
            nome, paginas, chars, seg, erro = fut.result()
            feitos += 1
            prefixo = f"[{feitos}/{len(pendentes)}]"
            if erro:
                print(f"{prefixo} ERRO {nome}: {erro}")
                continue
            aviso = ""
            if paginas and chars / paginas < 50:
                aviso = "  <- quase sem texto, provavelmente escaneado (precisa de OCR)"
            print(f"{prefixo} {nome}: {paginas} pág, {seg:.1f}s{aviso}")

    print(f"\nConcluído em {time.perf_counter() - inicio:.1f}s.")


if __name__ == "__main__":
    main()