---
name: monitor-orquestradora
description: Ponto de entrada do Monitor (material de estudo). Use quando o usuário pedir para processar, organizar, converter, indexar ou montar material de estudo a partir de uma pasta Monitor com "Materiais Base" (PDFs de aula, livro, provas anteriores, áudios de aula), ou chamar a orquestradora ou o Monitor pelo nome. Faz inventário, conversão e indexação com os scripts do plugin e depois aciona a skill monitor-analisar-topicos.
---

# Monitor — Orquestradora

Transforma a pasta bagunçada de originais (`## Materiais Base`) em transcrições
organizadas e num índice compacto, e passa isso para a skill de tópicos.
Quem decide o que é cada arquivo e o que já foi feito são **os scripts**, não a
leitura dos arquivos. Isso economiza token.

## Onde estão as coisas

- **Raiz do Monitor**: a pasta de trabalho do usuário, que contém
  `## Materiais Base`, `## Subprodutos` e `# Resultado Final`. Os nomes podem
  vir com ou sem `#`. Procure essa estrutura nas pastas conectadas; se houver
  mais de uma candidata, pergunte.
- **README.md da raiz**: leia primeiro. Ele descreve as pastas e o que é
  temporário.
- **Scripts**: ficam em `scripts/` na raiz deste plugin, dois níveis acima
  desta skill: `<pasta desta skill>/../../scripts/`. Chame esse caminho de
  `$S`. Se ele não existir, use as cópias que estiverem na raiz do Monitor
  (`Organizar/`, `IndexarQuestoes/`...).

Rode os comandos **com a raiz do Monitor como pasta atual**, ou passe
`--raiz "<raiz>"`.

## Onde rodar

- **Terminal na máquina do usuário** (pasta conectada com shell): rode tudo lá.
  É o único jeito de transcrever áudio, porque o Whisper roda local.
- **Só ponte de arquivos** (sem terminal na máquina): traga para o workspace a
  pasta Monitor **sem os áudios**, rode os scripts e grave de volta só o que
  mudou (`## Subprodutos/...` e `# Resultado Final/...`). Com áudio pendente
  nesse modo, não instale o Whisper: passe ao usuário o comando para rodar no
  computador dele.

Dependências: `pip install pymupdf pypdf reportlab` (e `faster-whisper` só para áudio).

## Passo a passo

### 0. Leia o README da raiz
Confirme a estrutura. Depois, compare rapidamente os nomes em `## Materiais
Base` com as transcrições em `## Subprodutos`. Se parecerem de **matérias
diferentes** (ex.: originais de cálculo e transcrições de estatística), pare e
pergunte. As transcrições são temporárias, e o usuário pode ter esquecido de
limpar a matéria anterior. Não apague nada por conta própria.

### 1. Inventário (não muda nada)
```
python "$S/Organizar/organizar.py"
```
O script classifica cada original por extensão, nome e formato da página
(slide horizontal = aula; retrato longo = livro; curto = prova). Ele diz o que
está **pronto**, o que está **pendente** e o que ficou **?**, e grava o
`catalogo.json`.

- Transcrição com o mesmo nome do original conta como pronta. Trecho no
  formato `nome_INICIO_FIM` (ex.: `livro_313_465.md`) fica ligado ao
  `nome.pdf` com offset `INICIO-1`, e o livro **não** é reconvertido.
- Arquivos **?**: pergunte ao usuário o tipo de todos de uma vez e rode de novo
  com `--tipo "nome.pdf=Livros"` (aula, livro, prova, audio).
- Classificação suspeita: confirme antes de converter.
- **"Transcrições sem PDF original"**: o índice e o resumo funcionam, mas o
  corte final não pega essas questões. Avise o usuário.

### 2. Conversão (só se houver pendente)
```
python "$S/Organizar/organizar.py" --executar
```
O script roda o `extraipdf.py` nos PDFs e o `transcrever.py` nos áudios, e
coloca cada saída na subpasta certa de `## Subprodutos`. Nunca use
`--refazer` sem o usuário pedir. Se o script avisar "precisa de OCR", diga ao
usuário qual arquivo é.

Não leia as transcrições para conferir a conversão. O relatório basta.

### 3. Indexação
```
python "$S/IndexarQuestoes/indexar.py"
```
Gera `## Subprodutos/indice.md`. Rode se algo foi convertido ou se o índice
não existe ou é mais velho que alguma transcrição. Confira só o resumo
impresso (questões por fonte). Se uma fonte vier com **0 questões**, avise:
provavelmente o formato dela é diferente.

### 4. Passa para a análise de tópicos
Carregue a skill **monitor-analisar-topicos** e siga a partir do passo 1 dela,
mantendo `$S` e a raiz.

Se o usuário só queria organizar e converter, pare aqui. Diga o que foi
convertido, o que ficou pendente e por quê.

## Regras
- Nunca mova nem apague nada de `## Materiais Base`.
- `## Subprodutos` (transcrições, catálogo, índice) é da matéria atual e
  temporário. Não apague sem pedido explícito; quando o usuário pedir para
  trocar de matéria, apague só arquivos, mantendo as subpastas.
- Erros de script: mostre a mensagem real ao usuário.
