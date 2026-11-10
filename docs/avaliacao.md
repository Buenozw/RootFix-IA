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
python scripts/indexar.py         # cria a base a partir das fichas
python scripts/avaliar_busca.py   # mede a busca e sugere o limiar
```

O limiar sugerido vai para o `.env` como `LIMIAR_SIMILARIDADE`.
