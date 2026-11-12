#!/usr/bin/env python3
"""
indexar.py — gera um índice compacto das transcrições do Monitor para a IA
não precisar ler todos os .md.

Lê ## Subprodutos (PDFs de Aula, Livros, Provas Anteriores, Áudio) e escreve:
  ## Subprodutos/indice.md    -> versão enxuta, é o que a skill lê
  ## Subprodutos/indice.json  -> mesma coisa estruturada (para o plano de corte)

O índice tem, para cada fonte:
  - mapa de seções (título -> páginas)
  - questões/exercícios: id, páginas, nº, seção e trecho do enunciado
  - aulas: "pág. úteis" = páginas que sobram depois de tirar as repetições da
    animação do beamer (slide que só revela mais um pedaço do seguinte)
  - livro: página impressa, além da página do PDF

Uso:
    python indexar.py                         # indexa tudo
    python indexar.py --raiz "C:/.../Monitor"
    python indexar.py ler "Livros/livro_313_465.md" 41-42   # imprime só essas páginas
    python indexar.py ler "PDFs de Aula/...md" 61 --limpo   # com acentos corrigidos
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

PASTAS = {"aula": "PDFs de Aula", "livro": "Livros", "prova": "Provas Anteriores", "audio": "Áudio"}
TRECHO = {"aula": 260, "livro": 260, "prova": 420}

# --------------------------------------------------------------------------- texto

_ACENTOS = {"´": "\u0301", "`": "\u0300", "˜": "\u0303", "ˆ": "\u0302", "¨": "\u0308", "¸": "\u0327"}
_LIGAS = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "\u00a0": " ", "\x00": ""}


def limpar(t: str) -> str:
    """Conserta acentos quebrados de PDF LaTeX ('Estat´ıstica' -> 'Estatística')."""
    for k, v in _LIGAS.items():
        t = t.replace(k, v)
    t = re.sub(r"([´`˜ˆ¨¸])\s?([A-Za-zıȷ])",
               lambda m: m.group(2).replace("ı", "i").replace("ȷ", "j") + _ACENTOS[m.group(1)], t)
    t = re.sub(r"([cC])\s?¸", lambda m: m.group(1) + "\u0327", t)
    return unicodedata.normalize("NFC", t)


def um_linha(t: str, n: int) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def paginas(md: str) -> list[tuple[int, str]]:
    partes = re.split(r"^## Página (\d+)\s*$", md, flags=re.M)
    return [(int(partes[i]), partes[i + 1].strip()) for i in range(1, len(partes), 2)]


def linhas(t: str) -> list[str]:
    return [l.strip() for l in t.splitlines() if l.strip()]


def sem_rodape(t: str) -> str:
    ls = linhas(t)
    if ls and re.fullmatch(r"\d{1,4}", ls[-1]):
        ls = ls[:-1]
    return re.sub(r"\s+", "", " ".join(ls))


def faixas(nums: list[int]) -> str:
    if not nums:
        return ""
    out, ini, ant = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == ant + 1:
            ant = n
            continue
        out.append(f"{ini}" if ini == ant else f"{ini}-{ant}")
        ini = ant = n
    out.append(f"{ini}" if ini == ant else f"{ini}-{ant}")
    return ",".join(out)


# --------------------------------------------------------------------------- aulas

RE_TIT_EXERC = re.compile(r"exerc|exemplo|solu[cç]|resolu|desafio|caso \d|aplica", re.I)
RE_NUM_AULA = re.compile(r"^\s*(\d{1,2}[a-z]?)\s*[-–]\s*\S")


def indexar_aula(pgs: list[tuple[int, str]], tag: str) -> dict:
    limpas = [(n, limpar(t)) for n, t in pgs]
    titulos = [(n, (linhas(t) or [""])[0]) for n, t in limpas]

    secoes, atual = [], None
    for n, tit in titulos:
        tit_c = um_linha(tit, 70)
        if atual and atual["titulo"] == tit_c:
            atual["paginas"].append(n)
        else:
            atual = {"titulo": tit_c, "paginas": [n]}
            secoes.append(atual)

    # blocos de exercício: páginas seguidas com título de exercício/solução
    blocos, bloco = [], None
    texto_pg = dict(limpas)
    for n, tit in titulos:
        corpo = texto_pg[n]
        m = next((RE_NUM_AULA.match(l) for l in linhas(corpo)[1:4] if RE_NUM_AULA.match(l)), None)
        num = m.group(1) if m else None
        eh_exerc = bool(RE_TIT_EXERC.search(tit))
        continua = bloco and n == bloco["paginas"][-1] + 1 and eh_exerc and \
            (num is None or bloco["numero"] in (None, num))
        if continua:
            bloco["paginas"].append(n)
            bloco["numero"] = bloco["numero"] or num
        elif eh_exerc:
            bloco = {"numero": num, "paginas": [n], "titulo": um_linha(tit, 40)}
            blocos.append(bloco)
        else:
            bloco = None

    secao_de = {}
    ultima = ""
    for s in secoes:
        if not RE_TIT_EXERC.search(s["titulo"]):
            ultima = s["titulo"]
        for p in s["paginas"]:
            secao_de[p] = ultima

    questoes = []
    for i, b in enumerate(blocos, 1):
        ps = b["paginas"]
        uteis = [p for j, p in enumerate(ps)
                 if j == len(ps) - 1 or not sem_rodape(texto_pg[ps[j + 1]]).startswith(sem_rodape(texto_pg[p])[:-1])]
        enunciado = " ".join(linhas(texto_pg[ps[0]])[1:])
        questoes.append({
            "id": f"{tag}-E{i}", "numero": b["numero"], "titulo": b["titulo"],
            "paginas": faixas(ps), "paginas_uteis": faixas(uteis),
            "secao": secao_de.get(ps[0], ""), "trecho": um_linha(enunciado, TRECHO["aula"]),
        })

    mapa = [{"titulo": s["titulo"], "paginas": faixas(s["paginas"])}
            for s in secoes if not RE_TIT_EXERC.search(s["titulo"])]
    return {"secoes": mapa, "questoes": questoes}


# --------------------------------------------------------------------------- livro

RE_SECAO_LIVRO = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{3,80})$")
RE_PROB_LIVRO = re.compile(r"^(\d{1,3})\.\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ(“\"])")


def pagina_impressa(t: str) -> int | None:
    for l in linhas(t)[:4] + linhas(t)[-2:]:
        if re.fullmatch(r"\d{1,4}", l):
            return int(l)
    return None


def indexar_livro(pgs: list[tuple[int, str]], tag: str) -> dict:
    secoes, questoes = [], []
    cap, secao, ultimo_num = None, "", 0
    impressas = {}
    atual = None
    for n, bruto in pgs:
        t = limpar(bruto)
        impressas[n] = pagina_impressa(t)
        for l in linhas(t):
            ms = RE_SECAO_LIVRO.match(l)
            if ms and not l.isupper():
                if ms.group(1) != cap:
                    cap, ultimo_num = ms.group(1), 0
                secao = f"{ms.group(1)}.{ms.group(2)} {ms.group(3).strip()}"
                secoes.append({"titulo": um_linha(secao, 70), "pagina": n, "impressa": impressas[n]})
                atual = None
                continue
            mp = RE_PROB_LIVRO.match(l)
            if mp and int(mp.group(1)) > ultimo_num and int(mp.group(1)) <= ultimo_num + 3:
                ultimo_num = int(mp.group(1))
                atual = {"numero": mp.group(1), "paginas": [n], "secao": um_linha(secao, 60),
                         "cap": cap, "texto": l[mp.end():]}
                questoes.append(atual)
                continue
            if atual is not None:
                if n not in atual["paginas"]:
                    atual["paginas"].append(n)
                if len(atual["texto"]) < TRECHO["livro"] + 40:
                    atual["texto"] += " " + l
    saida = []
    for q in questoes:
        ini = q["paginas"][0]
        saida.append({
            "id": f"{tag}-C{q['cap']}P{q['numero']}", "numero": q["numero"], "capitulo": q["cap"],
            "paginas": faixas(q["paginas"][:2]), "impressa": impressas.get(ini),
            "secao": q["secao"], "trecho": um_linha(q["texto"], TRECHO["livro"]),
        })
    offset = next((impressas[n] - n for n in impressas if impressas[n]), None)
    return {"secoes": secoes, "questoes": saida, "impressa_menos_pdf": offset}


# --------------------------------------------------------------------------- provas

RE_QUESTAO_PROVA = re.compile(r"^(teste|quest[aã]o|exerc[ií]cio|problema)\s*(\d{1,2})\b", re.I)


def indexar_prova(pgs: list[tuple[int, str]], tag: str) -> dict:
    questoes, atual = [], None
    for n, bruto in pgs:
        for l in linhas(limpar(bruto)):
            m = RE_QUESTAO_PROVA.match(l)
            if m:
                atual = {"numero": m.group(2), "paginas": [n], "texto": l[m.end():].strip(" .:-")}
                questoes.append(atual)
            elif atual is not None:
                if n not in atual["paginas"]:
                    atual["paginas"].append(n)
                if len(atual["texto"]) < TRECHO["prova"] + 40:
                    atual["texto"] += " " + l
    if not questoes:  # prova sem cabeçalho de questão: uma entrada por página
        questoes = [{"numero": None, "paginas": [n], "texto": limpar(t)} for n, t in pgs]
    return {"questoes": [{
        "id": f"{tag}-Q{q['numero'] or i}", "numero": q["numero"], "paginas": faixas(q["paginas"]),
        "trecho": um_linha(q["texto"], TRECHO["prova"]),
    } for i, q in enumerate(questoes, 1)]}


# --------------------------------------------------------------------------- geral

def tag_de(tipo: str, nome: str, usados: set) -> str:
    base = {"aula": "A", "livro": "L", "prova": "P", "audio": "T"}[tipo]
    m = re.search(r"(?:-\s*|aula\s*)(\d{1,2})\b", nome, re.I) if tipo == "aula" else None
    m = m or (re.search(r"(19|20)(\d{2})", nome) if tipo == "prova" else None)
    sufixo = (m.group(m.lastindex) if m else "")
    tag, k = f"{base}{sufixo}", 1
    while tag in usados:
        k += 1
        tag = f"{base}{sufixo}{chr(96 + k)}"  # A5b, Lb...
    usados.add(tag)
    return tag


def _norm_pasta(nome: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", nome) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.strip("# ").lower())


def pasta_sub(raiz: Path) -> Path:
    for p in raiz.iterdir():
        if p.is_dir() and _norm_pasta(p.name) == "subprodutos":
            return p
    sys.exit(f"Não achei a pasta de Subprodutos em {raiz}.")


def achar_raiz(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    # 1º a pasta atual (e acima), depois a pasta do script (e acima)
    atual, aqui = Path.cwd().resolve(), Path(__file__).resolve().parent
    for p in [atual, *atual.parents, aqui, *aqui.parents]:
        if p.is_dir() and any(x.is_dir() and _norm_pasta(x.name) == "subprodutos" for x in p.iterdir()):
            return p
    sys.exit("Não achei a pasta Monitor. Use --raiz.")


def indexar(raiz: Path) -> None:
    sub = pasta_sub(raiz)
    catalogo = {}
    if (sub / "catalogo.json").exists():
        catalogo = json.loads((sub / "catalogo.json").read_text(encoding="utf-8"))
    fontes, usados = [], set()
    for tipo, pasta in PASTAS.items():
        for arq in sorted((sub / pasta).glob("*")):
            if arq.suffix not in (".md", ".txt") or arq.name.endswith(".timestamps.txt"):
                continue
            texto = arq.read_text(encoding="utf-8", errors="replace")
            rel = arq.relative_to(raiz).as_posix()
            tag = tag_de(tipo, arq.stem, usados)
            fonte = {"tag": tag, "tipo": tipo, "md": rel,
                     "origem": catalogo.get(rel, {}).get("origem"),
                     "offset": catalogo.get(rel, {}).get("offset", 0)}
            if tipo == "audio":
                fonte.update(caracteres=len(texto))
            else:
                pgs = paginas(texto)
                fonte["n_paginas"] = len(pgs)
                fonte.update({"aula": indexar_aula, "livro": indexar_livro,
                              "prova": indexar_prova}[tipo](pgs, tag))
            fontes.append(fonte)

    (sub / "indice.json").write_text(json.dumps(fontes, ensure_ascii=False, indent=1), encoding="utf-8")

    out = ["# Índice do Monitor", "",
           "Páginas = posição no .md (= no PDF original, salvo indicação de offset). 'úteis' = sem os slides repetidos da animação.",
           "Para ler páginas: python indexar.py ler \"<pasta/arquivo.md>\" <páginas> --limpo", ""]
    nomes = {"aula": "AULAS", "livro": "LIVROS", "prova": "PROVAS ANTERIORES", "audio": "ÁUDIOS"}
    for tipo in PASTAS:
        grupo = [f for f in fontes if f["tipo"] == tipo]
        if not grupo:
            continue
        out += [f"## {nomes[tipo]}", ""]
        for f in grupo:
            orig = f["origem"] or "SEM PDF ORIGINAL"
            if f["origem"] and f["offset"]:
                orig += f" — no recorte use offset {f['offset']}"
            out.append(f"### [{f['tag']}] {Path(f['md']).stem}  ({f.get('n_paginas', '-')} pág.; original: {orig})")
            if tipo == "audio":
                out += [f"Transcrição com {f['caracteres']} caracteres: ler em partes.", ""]
                continue
            if tipo == "livro" and f.get("impressa_menos_pdf") is not None:
                out.append(f"Página impressa = página do PDF + {f['impressa_menos_pdf']}")
            if f.get("secoes"):
                if tipo == "aula":
                    out.append("Seções: " + " | ".join(f"{s['titulo']} ({s['paginas']})" for s in f["secoes"]))
                else:
                    out.append("Seções: " + " | ".join(f"{s['titulo']} (p.{s['pagina']}/imp.{s['impressa']})"
                                                       for s in f["secoes"]))
            out.append("")
            for q in f["questoes"]:
                extra = ""
                if tipo == "aula":
                    extra = f" úteis {q['paginas_uteis']} · {q['titulo']}" + (f" nº{q['numero']}" if q["numero"] else "")
                    extra += f" · seção: {q['secao']}" if q["secao"] else ""
                elif tipo == "livro":
                    extra = f" (imp. {q['impressa']}) · {q['secao']}"
                out.append(f"- **{q['id']}** p.{q['paginas']}{extra} — {q['trecho']}")
            out.append("")
    (sub / "indice.md").write_text("\n".join(out), encoding="utf-8")

    nq = sum(len(f.get("questoes", [])) for f in fontes)
    print(f"OK: {len(fontes)} fonte(s), {nq} questão(ões) -> {(sub / 'indice.md').relative_to(raiz)}")
    for f in fontes:
        print(f"  [{f['tag']}] {f['tipo']:<5} {Path(f['md']).name}: {len(f.get('questoes', []))} questões")


def ler(raiz: Path, arquivo: str, spec: str, limpo: bool) -> None:
    caminho = Path(arquivo)
    if not caminho.is_absolute():
        caminho = next((c for c in [raiz / arquivo, pasta_sub(raiz) / arquivo] if c.exists()), caminho)
    pgs = dict(paginas(caminho.read_text(encoding="utf-8", errors="replace")))
    alvo = set()
    for parte in spec.split(","):
        ini, _, fim = parte.partition("-")
        alvo.update(range(int(ini), int(fim or ini) + 1))
    for n in sorted(alvo):
        if n in pgs:
            print(f"## Página {n}\n\n{limpar(pgs[n]) if limpo else pgs[n]}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Índice compacto das transcrições do Monitor.")
    ap.add_argument("comando", nargs="?", default="indexar", choices=["indexar", "ler"])
    ap.add_argument("arquivo", nargs="?")
    ap.add_argument("paginas", nargs="?")
    ap.add_argument("--raiz")
    ap.add_argument("--limpo", action="store_true", help="corrige acentos quebrados ao ler")
    a = ap.parse_args()
    raiz = achar_raiz(a.raiz)
    if a.comando == "ler":
        if not (a.arquivo and a.paginas):
            ap.error('uso: indexar.py ler "<arquivo.md>" 12-14')
        ler(raiz, a.arquivo, a.paginas, a.limpo)
    else:
        indexar(raiz)


if __name__ == "__main__":
    main()
