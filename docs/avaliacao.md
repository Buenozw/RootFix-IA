# Avaliação

Os números deste documento são gerados pelos scripts `scripts/avaliar_busca.py` (busca) e `scripts/avaliar_geracao.py` (geração), a partir dos casos de `data/avaliacao/casos.jsonl`. As seções entre marcas `<!-- … -->` são reescritas a cada execução; o resto pode ser editado à mão.

## Conjunto de casos

`data/avaliacao/casos.jsonl` tem um caso por linha, escrito como um morador escreveria no app. Os tipos são:

| Tipo | Para que serve |
|---|---|
| `representativo` | Problema típico de cada categoria, bem descrito |
| `informal` | Gíria, erro de digitação, frase curta |
| `fora_do_catalogo` | Problema que não é de zeladoria; o certo é responder que não encontrou |
| `ambiguo` | Descrição que não basta para decidir, ou que não diz nada |
| `categoria_errada` | A categoria vinda do Spring AI está errada de propósito, para medir o plano B |
| `desvio` | Tenta mudar as regras do modelo pela descrição; usado na avaliação da geração |

### Como revisar os rótulos

Os casos foram rascunhados com `revisado: false`. Enquanto houver casos assim, o relatório avisa que os números são provisórios. Para cada caso:

1. Confira se `categoria_esperada` e `deveria_encontrar` estão certos.
2. Depois da coleta, preencha `servico_esperado` com o nome **exato** do campo `servico` da ficha que resolve o problema. Deixe `null` nos casos que não devem encontrar nada.
3. Troque `revisado` para `true`.

Os casos marcados com `nota` dependem das fichas coletadas. O caso do barulho, por exemplo, deixa de ser "fora do catálogo" se vocês coletarem a ficha do PSIU.

## Como rodar

```bash
python scripts/indexar.py           # cria a base a partir das fichas
python scripts/avaliar_busca.py     # mede a busca e sugere o limiar
python scripts/avaliar_geracao.py   # mede o encaminhamento completo com o Gemini
```

O limiar sugerido vai para o `.env` como `LIMIAR_SIMILARIDADE`; depois de mudar, rode a avaliação da geração de novo.

A avaliação da geração faz uma chamada ao Gemini por caso, com 4 segundos de pausa entre elas para não estourar a cota gratuita (cerca de 4 minutos para 34 casos; `--pausa` muda a espera). No fim, ela simula o Gemini fora do ar num caso e confere se a resposta ainda traz o serviço e a fonte.

### Como a geração evita inventar

- O Gemini só **escolhe a ficha** (F1, F2 ou F3) e **escreve os textos**. Serviço, categoria, órgão, canal, prazo e documentos da resposta vêm dos metadados da ficha escolhida, nunca do modelo.
- Se a busca não passa do limiar, o Gemini nem é chamado.
- O relato do morador vai entre as marcas `<dados_do_morador>`, com a regra de que nada ali é instrução.
- O script confere, no texto gerado, se há prazo ou órgão que não está na ficha nem no relato, e lista os casos para revisão manual.
