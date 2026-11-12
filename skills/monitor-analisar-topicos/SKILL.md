---
name: monitor-analisar-topicos
description: Monta o material de estudo do Monitor para tópicos escolhidos pelo usuário. Lê o índice e as transcrições (aulas, áudios, livro, provas anteriores), analisa a incidência nas provas, agrupa as questões por padrão de cobrança, escreve um resumo teórico e gera um PDF único (resumo + levantamento + questões recortadas dos PDFs originais). Use depois da monitor-orquestradora, ou direto quando o usuário pedir lista de questões, levantamento ou material para estudar tópicos de uma matéria cujas transcrições já estão em Monitor/Subprodutos.
---

# Monitor — Analisar tópicos e montar o material

Entrega um PDF em três blocos:

1. **Resumo** (4 a 5 páginas): a teoria dos tópicos, já aplicada.
2. **Levantamento**: (a) incidência nas provas anteriores e (b) direcionamento,
   com tópico → grupos de mesmo padrão → questões e a página de cada uma neste PDF.
3. **Questões**: as páginas originais recortadas, na ordem aula → livro → prova,
   cada uma carimbada com o código da questão.

Os comandos rodam com a **raiz do Monitor** como pasta atual: a pasta com
`## Materiais Base`, `## Subprodutos` e `# Resultado Final` (os `#` podem
variar). Os scripts ficam em `$S = <pasta desta skill>/../../scripts/`; se
não existir, use as cópias da raiz do Monitor. Sobre onde rodar, vale o mesmo
que diz a monitor-orquestradora.

## Economia de token: regras fixas

- **Comece pelo índice** (`## Subprodutos/indice.md`). Ele tem as seções de cada
  aula e de cada capítulo, e todas as questões com página e trecho.
- **Nunca leia um .md de aula ou de livro inteiro.** Para ver uma questão ou um
  trecho de teoria, leia só as páginas necessárias:
  ```
  python "$S/IndexarQuestoes/indexar.py" ler "PDFs de Aula/<arquivo>.md" 61-64 --limpo
  python "$S/IndexarQuestoes/indexar.py" ler "Livros/<arquivo>.md" 41-43 --limpo
  ```
- Nas aulas, prefira as **páginas úteis** do índice: são as versões completas dos
  slides com animação.
- **Provas anteriores** são curtas e podem ser lidas inteiras. Elas são a base da
  análise de incidência.
- **Áudio** (`Áudio/*.txt`): procure primeiro as palavras dos tópicos (Grep) e
  leia só os trechos em volta.
- Se o índice não existir ou estiver mais velho que alguma transcrição, rode
  `python "$S/IndexarQuestoes/indexar.py"` antes de começar.

## Códigos das questões

O índice dá a cada questão um código, e esse código acompanha a questão até o PDF:
- `A6-E8`: aula 6, 8º bloco de exercício. "p." são todas as páginas; "úteis",
  as que entram no recorte.
- `L-C12P14`: livro, capítulo 12, problema 14. "p." é a página do PDF;
  "imp." é a página impressa no livro.
- `P23-Q3`: prova de 2023, questão/teste 3.

Use o código em tudo: no levantamento, no plano e na conversa com o usuário.

## Passo a passo

### 1. Pergunte os tópicos
Leia as linhas de **Seções** das aulas no índice e proponha a lista de tópicos
que aparece nelas. O usuário confirma, corta ou acrescenta. Pergunte também o
nome do material (ex.: "Cálculo P2"). Não comece a análise sem os tópicos
confirmados.

Se o usuário já disser os tópicos no pedido, só confirme o recorte em uma frase
e siga.

### 2. Mapa de conteúdo
Para cada tópico, anote em que aula e em que páginas ele aparece, a partir das
seções do índice. Anote também as **variações** que a aula trata. Exemplos:
σ conhecida ou desconhecida; variâncias iguais ou diferentes; amostras
independentes ou emparelhadas; teste unilateral ou bilateral; aderência,
independência ou homogeneidade.
- Fonte principal: o PDF da aula.
- Se houver transcrição de áudio da mesma aula, use para completar: ênfases do
  professor, "isso cai na prova", atalhos de resolução.
- Esse mapa é de trabalho e não vai para o PDF. Ele orienta os passos 3 a 5.

### 3. Incidência nas provas anteriores
Leia cada prova e classifique cada questão por:
- **tópico** e **variação**, ligados ao mapa do passo 2;
- **forma de cobrança**: cálculo de IC, regra de decisão, valor-p, assertivas
  V/F sobre um mesmo enunciado, escolha do teste adequado, interpretação,
  cálculo de erro tipo II ou poder etc.

Conte por tópico e por forma de cobrança. O resultado diz **o que mais cai e de
que jeito cai**, e é ele que define a ordem de prioridade dos grupos no passo 4.
Questões de prova fora dos tópicos pedidos entram na contagem como "outros", mas
não no material.

### 4. Agrupe as questões por padrão
Junte **todas** as questões dos tópicos pedidos, de aulas, livro e provas, em
grupos de **mesmo padrão**: mesmo assunto e mesmo jeito de cobrar.
Exemplo: dentro de "IC para diferença de médias, σ conhecida", o Grupo 1 é
"cálculo direto do IC e interpretação" e o Grupo 2 é "tamanho de amostra para
uma margem de erro".

- Classifique pelo trecho do índice. Quando o trecho não bastar, leia as
  páginas da questão com `ler --limpo`.
- No livro, use as seções como filtro: problema de seção fora dos tópicos não
  entra. O índice do livro pode trazer algum item numerado que não é problema;
  descarte quando o texto mostrar isso.
- Ordene os grupos de cada tópico pela incidência do passo 3. O padrão que mais
  cai vem primeiro, e grupo sem nenhuma questão de prova vem por último.
- Aponte **lacunas**: padrão que cai em prova e tem pouca ou nenhuma questão
  para treinar.
- Se o total passar de umas 80 questões, mostre ao usuário a contagem por
  tópico e pergunte se ele quer tudo ou só os grupos de maior incidência.

### 5. Escreva o resumo (Bloco 1)
De 4 a 5 páginas no total, para todos os tópicos juntos. A **teoria vem do
livro**: leia, com `ler --limpo`, só as páginas das seções ligadas aos tópicos.
As **aulas** servem para a notação e as fórmulas como o professor usa.
Para cada tópico:
- quando usar, ou seja, como reconhecer pelo enunciado;
- estatística ou pivô, distribuição e graus de liberdade;
- IC e/ou regra de decisão (unilateral e bilateral) e valor-p;
- armadilhas comuns;
- no máximo um exemplo numérico curto, só quando ajudar.

Termine com uma tabela de decisão: qual teste ou IC usar em cada situação.
Escreva em `resumo.md` (formato abaixo).

### 6. Escreva o levantamento (Bloco 2)
Escreva em `levantamento.md`:
- **2a. Incidência**: uma tabela com tópico × prova × forma de cobrança, seguida
  de 3 a 5 linhas de leitura (o que mais cai, como cai, o que nunca caiu).
- **2b. Direcionamento**: para cada tópico, na ordem de prioridade, os grupos
  com uma linha de descrição do padrão. Depois, as questões do grupo separadas
  por fonte (Aulas / Livro / Provas), cada uma com o código, a referência de
  origem e a página neste PDF, assim:
  `- A5-E1 · Aula 5, p. 7–8, ex. 13 · pág. {{pg:A5-E1}}`
  `- L-C11P41 · livro p. impressa 331, probl. 41 · pág. {{pg:L-C11P41}}`
- **Lacunas** no fim.

`{{pg:CÓDIGO}}` é substituído pelo `montar.py` pelo número da página real.

### 7. Monte o plano e o PDF (Bloco 3)
Pasta de saída: `# Resultado Final/<nome-do-material> <AAAA-MM-DD>/`, na raiz
do Monitor, com `resumo.md`, `levantamento.md` e `plano.json`. Esta é a única
pasta que fica; os subprodutos são temporários.

O `plano.json` lista as questões **na ordem do Bloco 3**: todas as das aulas
(em ordem de aula e de página), depois as do livro, depois as das provas. Cada
questão aparece uma vez, mesmo que esteja em vários grupos.
```json
{
  "titulo": "Estatística",
  "resumo": "resumo.md",
  "levantamento": "levantamento.md",
  "carimbo": true,
  "questoes": [
    {"id": "A5-E1", "grupo": "Aulas", "arquivo": "../../## Materiais Base/<aula>.pdf",
     "paginas": "8", "rotulo": "Aula 5 — ex. 13"},
    {"id": "L-C11P41", "grupo": "Livro", "arquivo": "../../## Materiais Base/<livro>.pdf",
     "paginas": "36"},
    {"id": "P23-Q3", "grupo": "Provas anteriores", "arquivo": "../../## Materiais Base/P2 2023.pdf",
     "paginas": "2"}
  ]
}
```
- `arquivo`: o original de cada fonte, que está no índice ("original: ...")
  e no `catalogo.json` (campo `origem`), com caminho relativo à pasta do
  plano (normalmente `../../` + origem). Para aula, use as **páginas úteis**.
- As páginas do índice são as do .md. Quando o índice disser "no recorte use
  offset N" (ex.: livro transcrito em trecho), ponha `"offset": N` em cada
  questão dessa fonte. Exemplo: livro p.47 com offset 312 vira a página 359 do
  `livro.pdf`.
- Fonte sem original (`origem: null`): monte o PDF sem essas questões, mantenha
  as linhas delas no levantamento e diga ao usuário quais PDFs faltam.

Rode:
```
python "$S/MontarMaterial/montar.py" --plano "<pasta>/plano.json" -o "<pasta>/<nome-do-material>.pdf"
```
O script resolve os `{{pg:...}}`, coloca páginas divisórias entre Aulas, Livro
e Provas, carimba o código em cada página e cria marcadores navegáveis.

### 8. Confira antes de entregar
- Leia os **AVISOS** do script. Código citado que não está no plano, ou página
  que não bateu, são erros a corrigir.
- Abra o PDF e confira o número de páginas. Renderize uma página do resumo e uma
  do levantamento para ver se tabelas e fórmulas saíram certas.
- Sorteie duas questões do Bloco 3 e confira se a página carimbada é mesmo a
  questão citada.

### 9. Entregue
Em poucas linhas: o caminho do PDF, quantas páginas e questões ele tem, os dois
ou três achados principais da incidência e as lacunas. Não repita o levantamento
na conversa.

## Formato dos .md (o que o montar.py entende)
- `#`, `##`, `###`; listas com `- ` ou `1. `; `**negrito**`, `*itálico*`.
- Tabelas com `|` e linha de separação `|---|`.
- Letras gregas e símbolos direto em Unicode: μ σ α β χ² √ ≤ ≥ ± ≠ Σ X̄.
- Subscrito `x_{1}`; sobrescrito `σ^{2}`. Nada de LaTeX com `$...$`.
- `<!-- quebra -->` sozinho numa linha força página nova.
- O resumo deve caber em 4 a 5 páginas A4. Prefira tabelas e listas curtas a
  parágrafos longos.
