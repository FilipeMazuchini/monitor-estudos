#!/usr/bin/env python3
"""
organizar.py — inventário da pasta "Materiais Base" do Monitor.

Descobre o que é cada arquivo (aula, livro, prova, áudio), diz o que já foi
convertido e, com --executar, roda os scripts certos e coloca o resultado na
subpasta certa de "## Subprodutos". Também grava ## Subprodutos/catalogo.json,
que liga cada .md ao arquivo original (o montar.py precisa disso no fim).

Transcrições que já existem NÃO são refeitas:
  - mesmo nome do original            -> pronto
  - nome_INICIO_FIM (trecho cortado)  -> ligado ao original com offset INICIO-1
    ex.: livro_313_465.md -> livro.pdf, páginas +312
Os nomes das pastas são achados ignorando '#' e acentos.

Uso (a partir de qualquer lugar):
    python organizar.py                     # só inventário, não muda nada
    python organizar.py --executar          # converte o que falta
    python organizar.py --executar --refazer
    python organizar.py --tipo "arquivo.pdf=Livros"   # corrige uma classificação
    python organizar.py --raiz "C:/.../Monitor"       # se o script estiver fora da pasta

Classificação (nesta ordem):
  1. extensão de áudio                       -> Áudio
  2. palavra-chave no nome do arquivo        -> livro/prova/aula
  3. formato das páginas do PDF:
       maioria horizontal (slides)           -> PDFs de Aula
       retrato com mais de 40 páginas        -> Livros
       retrato com até 20 páginas            -> Provas Anteriores
  4. não deu para decidir                    -> "?" (a skill pergunta a você)
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent  # pasta com ExtraiPDF/, Transcript/...
AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus", ".mp4"}
PASTAS = {
    "aula": "PDFs de Aula",
    "livro": "Livros",
    "prova": "Provas Anteriores",
    "audio": "Áudio",
}
NOMES_TIPO = {v: k for k, v in PASTAS.items()} | {k: k for k in PASTAS}

RE_LIVRO = re.compile(r"\b(livro|book|cap(itulo)?|chapter|bussab|morettin)\b", re.I)
RE_PROVA = re.compile(
    r"\b(prova|exame|psub|prec|gabarito)\b|\bp\s*[1-3]\s*[-_ ]?\s*(19|20)\d{2}\b", re.I
)
RE_AULA = re.compile(r"\b(aula|slides?|lecture|apresenta)", re.I)


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _norm_pasta(nome: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(nome).strip("# ").lower())


def achar_pasta(raiz: Path, chave: str) -> Path:
    """Acha a pasta pelo nome, ignorando '#' e acentos ('## Materiais Base' == 'Materiais Base')."""
    for p in raiz.iterdir():
        if p.is_dir() and _norm_pasta(p.name) == chave:
            return p
    padrao = {"materiais base": "## Materiais Base", "subprodutos": "## Subprodutos",
              "resultado final": "# Resultado Final"}[chave]
    return raiz / padrao


def geometria_pdf(caminho: Path) -> tuple[int, float]:
    """(n_paginas, fração de páginas horizontais) — lê só as 15 primeiras."""
    try:
        import fitz  # PyMuPDF (mesmo pacote do extraipdf)
        with fitz.open(caminho) as d:
            n = d.page_count
            amostra = [d[i].rect for i in range(min(n, 15))]
    except ImportError:
        from pypdf import PdfReader
        r = PdfReader(str(caminho))
        n = len(r.pages)
        amostra = [r.pages[i].mediabox for i in range(min(n, 15))]
    horiz = sum(1 for b in amostra if float(b.width) > float(b.height))
    return n, (horiz / len(amostra)) if amostra else 0.0


def classificar(arq: Path) -> tuple[str, str]:
    """Retorna (tipo, motivo)."""
    ext = arq.suffix.lower()
    if ext in AUDIO:
        return "audio", "extensão de áudio"
    if ext != ".pdf":
        return "?", f"extensão {ext} não tratada"
    nome = sem_acento(arq.stem)
    if RE_PROVA.search(nome):
        return "prova", "nome do arquivo"
    if RE_LIVRO.search(nome):
        return "livro", "nome do arquivo"
    try:
        n, frac_h = geometria_pdf(arq)
    except Exception as e:
        return "?", f"não consegui abrir o PDF ({e})"
    if RE_AULA.search(nome) or frac_h >= 0.6:
        return "aula", f"slides horizontais ({n} pág.)" if frac_h >= 0.6 else "nome do arquivo"
    if n > 40:
        return "livro", f"retrato, {n} páginas"
    if n <= 20:
        return "prova", f"retrato, {n} páginas"
    return "?", f"retrato, {n} páginas (entre prova e livro)"


def destino_md(raiz_sub: Path, tipo: str, arq: Path) -> Path:
    ext = ".txt" if tipo == "audio" else ".md"
    return raiz_sub / PASTAS[tipo] / f"{arq.stem}{ext}"


def ja_convertido(md: Path, origem: Path) -> bool:
    return md.exists() and md.stat().st_mtime >= origem.stat().st_mtime


def converter_pdf(raiz: Path, arq: Path, md: Path) -> str:
    script = SCRIPTS / "ExtraiPDF" / "extraipdf.py"
    r = subprocess.run([sys.executable, str(script), str(arq), "--refazer"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    gerado = arq.with_suffix(".md")
    if not gerado.exists():
        return f"ERRO: {r.stdout[-300:]}{r.stderr[-300:]}"
    md.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(gerado), str(md))
    aviso = " (quase sem texto: provavelmente escaneado, precisa de OCR)" if "OCR" in r.stdout else ""
    return "ok" + aviso


def transcrever_pasta(raiz: Path, pasta_audio: Path, saida: Path, modelo: str, idioma: str) -> str:
    """O transcrever.py é interativo: respondemos as perguntas pelo stdin."""
    script = SCRIPTS / "Transcript" / "transcrever.py"
    saida.mkdir(parents=True, exist_ok=True)
    respostas = "\n".join([str(pasta_audio), modelo, idioma, "auto", str(saida)]) + "\n"
    r = subprocess.run([sys.executable, str(script)], input=respostas, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return "ok" if r.returncode == 0 else f"ERRO: {r.stderr[-400:]}"


def achar_raiz(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    # 1º a pasta atual (e acima), depois a pasta do script (e acima)
    atual, aqui = Path.cwd().resolve(), Path(__file__).resolve().parent
    for p in [atual, *atual.parents, aqui, *aqui.parents]:
        if p.is_dir() and any(_norm_pasta(x.name) in ("materiais base", "subprodutos")
                              for x in p.iterdir() if x.is_dir()):
            return p
    sys.exit("Não achei a pasta Monitor. Use --raiz.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inventário e conversão dos Materiais Base.")
    ap.add_argument("--raiz", help="pasta Monitor")
    ap.add_argument("--executar", action="store_true", help="converte o que falta")
    ap.add_argument("--refazer", action="store_true", help="reconverte tudo")
    ap.add_argument("--tipo", action="append", default=[],
                    help='força classificação: "nome.pdf=Livros" (aula|livro|prova|audio)')
    ap.add_argument("--modelo", default="small", help="modelo Whisper (padrão small)")
    ap.add_argument("--idioma", default="pt")
    a = ap.parse_args()

    raiz = achar_raiz(a.raiz)
    base, sub = achar_pasta(raiz, "materiais base"), achar_pasta(raiz, "subprodutos")
    achar_pasta(raiz, "resultado final").mkdir(exist_ok=True)
    for pasta in PASTAS.values():
        (sub / pasta).mkdir(parents=True, exist_ok=True)

    forcados = {}
    for f in a.tipo:
        nome, _, t = f.partition("=")
        t = NOMES_TIPO.get(t.strip()) or NOMES_TIPO.get(sem_acento(t.strip()).lower())
        if not t:
            sys.exit(f"--tipo inválido: {f}")
        forcados[nome.strip().lower()] = t

    arquivos = sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
    catalogo_path = sub / "catalogo.json"
    catalogo = json.loads(catalogo_path.read_text(encoding="utf-8")) if catalogo_path.exists() else {}

    # .md já existentes em #Subprodutos, por tipo (stem -> caminho)
    existentes = {t: {m.stem: m for m in (sub / pp).glob("*")
                      if m.suffix in (".md", ".txt") and not m.name.endswith(".timestamps.txt")}
                  for t, pp in PASTAS.items()}
    pendencias, duvidas, pastas_audio = [], [], {}
    print(f"Monitor: {raiz}\nMateriais Base: {len(arquivos)} arquivo(s)\n")
    for arq in arquivos:
        tipo, motivo = classificar(arq)
        if arq.name.lower() in forcados:
            tipo, motivo = forcados[arq.name.lower()], "definido por você"
        rel = arq.relative_to(raiz).as_posix()
        if tipo == "?":
            duvidas.append(rel)
            print(f"  ?      {rel}  — {motivo}")
            continue
        md = destino_md(sub, tipo, arq)
        trechos = [m for st, m in existentes[tipo].items()
                   if re.fullmatch(re.escape(arq.stem) + r"_(\d+)_(\d+)", st)]
        if trechos and not md.exists():
            # transcrição de um trecho (convenção do cortapdf: nome_INICIO_FIM)
            for m in trechos:
                ini = int(re.search(r"_(\d+)_\d+$", m.stem).group(1))
                catalogo[m.relative_to(raiz).as_posix()] = {"origem": rel, "tipo": tipo, "offset": ini - 1}
                print(f"  {tipo:<6} {rel}  — trecho já transcrito: {m.name} (páginas +{ini - 1}) — pronto")
            continue
        feito = (md.exists() and not a.refazer) if catalogo.get(md.relative_to(raiz).as_posix(), {}).get("origem") is None \
            else (ja_convertido(md, arq) and not a.refazer)
        status = "pronto" if feito else "pendente"
        print(f"  {tipo:<6} {rel}  — {motivo} — {status}")
        catalogo[md.relative_to(raiz).as_posix()] = {"origem": rel, "tipo": tipo}
        if not feito:
            if tipo == "audio":
                pastas_audio.setdefault(arq.parent, []).append(arq)
            else:
                pendencias.append((arq, md))

    # .md que já existem sem original em Materiais Base (feitos à mão)
    sem_origem = []
    for tipo, pasta in PASTAS.items():
        for md in sorted((sub / pasta).glob("*")):
            if md.suffix not in (".md", ".txt") or md.name.endswith(".timestamps.txt"):
                continue
            chave = md.relative_to(raiz).as_posix()
            if chave not in catalogo:
                catalogo[chave] = {"origem": None, "tipo": tipo}
            if catalogo[chave]["origem"] is None:
                sem_origem.append(chave)

    if a.executar:
        for arq, md in pendencias:
            print(f"\nConvertendo {arq.name} -> {md.relative_to(raiz)}: ", end="", flush=True)
            print(converter_pdf(raiz, arq, md))
        for pasta, audios in pastas_audio.items():
            print(f"\nTranscrevendo {len(audios)} áudio(s) de {pasta.name}: ", end="", flush=True)
            print(transcrever_pasta(raiz, pasta, sub / PASTAS["audio"], a.modelo, a.idioma))
    elif pendencias or pastas_audio:
        n = len(pendencias) + sum(len(v) for v in pastas_audio.values())
        print(f"\n{n} arquivo(s) pendente(s). Rode com --executar para converter.")

    catalogo = {k: v for k, v in sorted(catalogo.items()) if (raiz / k).exists()}  # tira .md apagados
    catalogo_path.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")

    if duvidas:
        print("\nNÃO CLASSIFICADOS (use --tipo \"nome=Livros\" etc.):")
        for d in duvidas:
            print("  -", d)
    if sem_origem:
        print("\nTRANSCRIÇÕES SEM PDF ORIGINAL em Materiais Base (o corte final não vai achar as páginas):")
        for s in sem_origem:
            print("  -", s)
    print(f"\nCatálogo: {catalogo_path.relative_to(raiz)}")


if __name__ == "__main__":
    main()
