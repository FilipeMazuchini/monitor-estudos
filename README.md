# Monitor

Plugin para o Claude que monta **material de estudo** de qualquer matéria a
partir de PDFs de aula, livro, provas anteriores e áudios de aula. O produto
final é um PDF em três blocos:

1. **Resumo** (4 a 5 páginas): a teoria dos tópicos escolhidos, já aplicada.
2. **Levantamento**: incidência de cada tópico nas provas anteriores e
   questões agrupadas por padrão de cobrança, com a página de cada uma.
3. **Questões**: as páginas originais recortadas, na ordem aula → livro → prova.

## Instalação

No Claude (app desktop ou Claude Code):

```
/plugin marketplace add FilipeMazuchini/<nome-do-repositório>
/plugin install monitor
```

Os scripts precisam de Python 3.10+ e das dependências:

```
pip install -r requirements.txt
```

`faster-whisper` só é necessário para transcrever áudio (roda localmente).

## Como usar

1. Crie uma pasta de trabalho chamada `Monitor` com esta estrutura:

   | Pasta | O que vai nela |
   |---|---|
   | `## Materiais Base/` | Os originais da matéria, soltos: PDFs de aula, livro, provas, áudios |
   | `## Subprodutos/` | Transcrições geradas pelos scripts (temporário) |
   | `# Resultado Final/` | Uma pasta por material gerado (PDF final, resumo, levantamento) |

   Os nomes podem ter ou não `#`: os scripts acham as pastas ignorando `#` e acentos.

2. Conecte a pasta ao Claude e peça, por exemplo, **"roda o Monitor"** ou
   **"monta o material da P2"**.

3. O Claude pergunta os tópicos, analisa as provas e entrega o PDF em
   `# Resultado Final/`.

## Skills

- **monitor-orquestradora**: ponto de entrada. Faz o inventário dos originais,
  converte só o que falta (PDF → .md, áudio → .txt) e gera um índice compacto
  de seções e questões.
- **monitor-analisar-topicos**: incidência nas provas, agrupamento por padrão,
  resumo teórico e PDF final.

## Scripts (`scripts/`)

| Script | Função |
|---|---|
| `Organizar/organizar.py` | Classifica os originais e converte o que falta |
| `ExtraiPDF/extraipdf.py` | PDF → .md com marcadores `## Página N` |
| `Transcript/transcrever.py` | Áudio → .txt (Whisper local) |
| `IndexarQuestoes/indexar.py` | Índice de seções/questões e leitura de páginas |
| `CortarPDF/cortapdf.py` | Recorta páginas de um PDF |
| `MontarMaterial/montar.py` | Monta o PDF final com referências de página e carimbo |

Também dá para rodá-los à mão, de dentro da pasta `Monitor`:

```
python <plugin>/scripts/Organizar/organizar.py                # inventário
python <plugin>/scripts/Organizar/organizar.py --executar     # converte o que falta
python <plugin>/scripts/IndexarQuestoes/indexar.py            # gera o índice
python <plugin>/scripts/CortarPDF/cortapdf.py livro.pdf --paginas "313-465" -o livro_313_465.pdf
python <plugin>/scripts/MontarMaterial/montar.py --plano "# Resultado Final/<pasta>/plano.json" -o "<pasta>/Material.pdf"
```

## Regras

- Nada já transcrito é refeito: uma transcrição com o mesmo nome do original conta como pronta.
- Trecho de um PDF maior usa o nome `original_INICIO_FIM` (ex.: `livro_313_465`),
  e o corte final aponta para as páginas certas do livro inteiro.
- Os originais em `## Materiais Base` nunca são movidos nem apagados.
- **Trocar de matéria:** apague o conteúdo das subpastas de `## Subprodutos`
  (mantenha as pastas), troque os originais e peça para rodar de novo.

## Licença

MIT. Os materiais de estudo que você processar são seus; não os publique se
tiverem direitos autorais de terceiros.
