# Composição Musical Algorítmica com Cadeias de Markov: Geração Simbólica de Lead & Drums

Trabalho Prático 1 — DCC831 IA Generativa para Música (UFMG)

Sistema de composição musical **simbólica e reativa**: uma gravação simulada de
corrida (você, oponente e polícia, cada um em `0..1`) é amostrada periodicamente
e dirige cadeias de Markov treinadas em loops compostos à mão no LMMS, em 4/4 e
7/8. A cada compasso o estado do jogo decide a métrica (4/4 quando à frente,
7/8 quando atrás), quais instrumentos tocam e a temperatura de amostragem. A
saída é um `.mid` reproduzível, renderizado em áudio com FluidSynth.

📄 **Relatório (ISMIR, 2 páginas):** [`paper/tp1_musica.pdf`](paper/tp1_musica.pdf)

## Músicas geradas

Cinco peças, todas reproduzíveis a partir das mesmas entradas. Cada pasta em
`output/` contém o áudio (`.ogg`), o simbólico (`.mid`), o registro por compasso
(`.sync.json`) e a configuração da execução (`.run.json`).

| peça | ouvir/baixar | MIDI | corrida | ordem | semente | latch | temp. |
|---|---|---|---|---|---|---|---|
| comeback-a — baseline | [ogg](output/comeback-a/comeback.ogg) | [mid](output/comeback-a/comeback.mid) | comeback | 1 | 11 | 1 | 0.9 |
| comeback-a2 — mesma configuração, outra semente | [ogg](output/comeback-a2/comeback.ogg) | [mid](output/comeback-a2/comeback.mid) | comeback | 1 | 12 | 1 | 0.9 |
| comeback-b — ordem 2 ⭐ | [ogg](output/comeback-b/comeback.ogg) | [mid](output/comeback-b/comeback.mid) | comeback | 2 | 23 | 1 | 0.9 |
| comeback-c — ordem 3 | [ogg](output/comeback-c/comeback.ogg) | [mid](output/comeback-c/comeback.mid) | comeback | 3 | 31 | 1 | 0.9 |
| domination-a — caso-controle ⭐ | [ogg](output/domination-a/domination.ogg) | [mid](output/domination-a/domination.mid) | domination | 2 | 5 | 4 | 1.15 |

⭐ = favoritas apontadas no relatório. "latch" = a cada quantos compassos o
estado do jogo é reamostrado (hiperparâmetro `sample_every_bars`).

## Método

1. **Composição (LMMS)** — loops em 4/4 e 7/8 com TripleOscillator (lead) e SF2
   Player / General User GS (bateria), exportados em MIDI.
2. **Tokenização** (`tools/import_loops.py`, `engine/corpus.py`) — grade de
   semicolcheia (32 ticks): um token por passo são as notas que *começam* ali,
   com altura e duração em passos; bateria vira nomes de vozes GM; `()` = nada
   começa (pausa ou sustentação). Silêncio final por instrumento é removido.
3. **Cadeias de Markov** (`engine/markov.py`) — uma cadeia por instrumento ×
   métrica (4 cadeias), ordem configurável (padrão 2); probabilidades obtidas
   por contagem das transições observadas, normalizadas por contexto, com
   *backoff* progressivo de ordem n até 1 quando o histórico não aparece no
   corpus; amostragem ponderada com temperatura.
4. **Reatividade** (`engine/hooks.py`, `engine/generate.py`) — o estado da
   corrida é amostrado a cada `sample_every_bars` compassos e decide métrica,
   camadas ativas e temperatura.
5. **Saída** — `.mid` via mido, registro `.sync.json` por compasso e áudio via
   FluidSynth CLI + soundfont General User GS (`tools/render_audio.py`).

Detalhes técnicos: [`docs/engine.md`](docs/engine.md) (motor) e
[`docs/contracts.md`](docs/contracts.md) (formatos JSON).

## Resultados

**Reatividade** — nas peças de comeback, 100% dos compassos em 7/8 ocorrem
quando o jogador está atrás; no caso-controle (sempre à frente), 0% em 7/8.

| peça | compassos | duração | 7/8 % | 7/8 quando atrás | drums | lead | tensão méd/máx |
|---|---|---|---|---|---|---|---|
| comeback-a | 103 | 165 s | 50% | 100% | 82% | 88% | 0.61 / 1.00 |
| comeback-a2 | 103 | 165 s | 50% | 100% | 82% | 88% | 0.61 / 1.00 |
| comeback-b | 103 | 165 s | 50% | 100% | 82% | 88% | 0.61 / 1.00 |
| comeback-c | 103 | 165 s | 50% | 100% | 82% | 88% | 0.61 / 1.00 |
| domination-a | 88 | 151 s | 0% | — | 100% | 55% | 0.46 / 0.60 |

**Memorização** (Tabela 1 do relatório) — maior trecho gerado idêntico ao corpus
e fração de passos cobertos por trechos de ≥ 4 passos:

| peça | ordem | passos | maior trecho idêntico | cobertura ≥ 4 passos |
|---|---|---|---|---|
| comeback-a | 1 | 2630 | 13 | 78% |
| comeback-a2 | 1 | 2630 | 13 | 75% |
| comeback-b | 2 | 2630 | 29 | 100% |
| comeback-c | 3 | 2630 | 28 | 100% |
| domination-a | 2 | 2176 | 20 | 100% |

**Mesma configuração, sementes distintas** — `comeback-a` vs `comeback-a2`:
36% dos tokens coincidem (drums 464/1278; lead 485/1352) — peças diferentes a
partir da mesma configuração.

## Instalação e reprodução

Requisitos: Python 3, `ffmpeg` e `fluidsynth` (Arch: `sudo pacman -S fluidsynth ffmpeg`).

```bash
bash tools/setup.sh                     # venv + mido + soundfont General User GS
.venv/bin/python tools/import_loops.py  # corpus/*.mid -> corpus/corpus.json
bash tools/run_all.sh                   # gera as 5 peças, renderiza, valida e relata
```

`run_all.sh` escreve também `output/report-stats.md`,
`output/report-memorization.md` e `output/report-same-config.md`. Para uma peça
individual:

```bash
.venv/bin/python -m engine --race races/comeback.json --corpus corpus/corpus.json \
    --config configs/pieces/comeback-b.json --out output/comeback-b
.venv/bin/python tools/render_audio.py --mid output/comeback-b/comeback.mid \
    --out output/comeback-b/comeback.ogg
```

Dependências Python: [`requirements.txt`](requirements.txt) (`mido`).

## Estrutura do repositório

```
races/        gravações de corrida (gm-race/1): comeback e domination
corpus/       loops autorais: even/ (4/4) e odd/ (7/8) + corpus.json tokenizado
engine/       motor: race, hooks, markov, generate, midi_out, corpus, cli
configs/      hiperparâmetros: base.json + pieces/*.json
tools/        import_loops, render_audio, validate, stats, memorization,
              compare_pieces, run_all.sh, setup.sh, smoke_test.py
output/       peças geradas + relatórios das análises
paper/        tp1_musica.pdf
docs/         engine.md, contracts.md, conversa-pesquisa-ia.md
```

## Declaração de uso de IA

> TODO antes da submissão: inserir os links das conversas de desenvolvimento.

Ferramentas de IA foram usadas como **apoio**: geração de código auxiliar
(importador do corpus, motor de geração, escritores de MIDI/registro, render,
validação e análises), gerenciamento de ambiente de teste, pesquisa
bibliográfica, instalação de dependências, testes automatizados, prototipação
de experimentos e formatação do relatório. A implementação do método —
tokenização, cadeia de Markov (`engine/markov.py`) e regras de reação ao jogo
(`engine/hooks.py`) — e o texto do relatório são de autoria do estudante; a IA
também aplicou correções mecânicas pontuais nesses arquivos a pedido do autor.
Conversas:

- Primeira conversa de pesquisa: [`docs/conversa-pesquisa-ia.md`](docs/conversa-pesquisa-ia.md)
- Desenvolvimento: **TODO (links das conversas)**

## Referências

[1] A. Prechtl, R. Laney, A. Willis, and R. Samuels, "Algorithmic music as
intelligent game music," in *Proc. of the AISB50*, London, UK, Apr. 2014.
