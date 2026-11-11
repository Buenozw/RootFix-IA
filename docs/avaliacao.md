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

## Testes de integração com a API Java (manuais)

Feitos com `scripts/testar_integracao.py`, a API Java no Render e a conta de gestor de teste.

| Data | Problema | Base na hora | Resultado | Análise |
|---|---|---|---|---|
| 10/11 | 2 · Buraco grande na avenida principal (Bela Vista, categoria Buraco ou pavimento) | 1 ficha: tapa-buraco da Subprefeitura Ipiranga | `encontrado: false` em 16,8 s; motivo: a ficha vale só para a Subprefeitura Ipiranga e o problema é na Bela Vista | Recusa correta. A Bela Vista é atendida pela Subprefeitura Sé; aceitar a ficha do Ipiranga mandaria o gestor cobrar o órgão errado, porque o órgão da resposta sai da ficha. Mostra que a regra "use só o que está na ficha" protege contra encaminhamento errado, e que a cobertura depende de ter fichas da subprefeitura de cada comunidade. |

O tempo de 16,8 s veio quase todo da geração com o raciocínio padrão do modelo. Depois disso o serviço passou a pedir raciocínio mínimo (`GEMINI_RACIOCINIO=minimal`); a comparação de tempo entra na próxima linha desta tabela.

<!-- busca:inicio -->

## Avaliação da busca (RAG)

> **Atenção:** 34 de 34 casos ainda não tiveram o rótulo revisado (`revisado: false` em `casos.jsonl`). Os números abaixo são provisórios.

> O acerto por **serviço** e o MRR aparecem depois que `servico_esperado` for preenchido nos casos, com o nome exato do serviço da ficha.

34 casos, 29 com serviço esperado na base. Limiar usado: 0.70.

| Métrica | Com filtro por categoria | Sem filtro |
|---|---|---|
| Categoria certa em 1º | 14% | 14% |
| Categoria certa no top-3 | 14% | 14% |
| Serviço certo em 1º | — | — |
| Serviço certo no top-3 | — | — |
| MRR do serviço | — | — |

### Acerto da categoria em 1º, por categoria

| Categoria | Acertos | Casos |
|---|---|---|
| Buraco ou pavimento | 4 | 4 |
| Iluminação pública | 0 | 5 |
| Lixo e limpeza | 0 | 4 |
| Bueiro e drenagem | 0 | 4 |
| Calçada e acessibilidade | 0 | 3 |
| Sinalização de trânsito | 0 | 3 |
| Praças e áreas verdes | 0 | 4 |
| Outros | 0 | 2 |

### Quando o Spring AI erra a categoria

Em 3 casos com a categoria errada de propósito, a busca filtrada ficou abaixo do limiar e caiu no plano B (base toda) em 3; a categoria certa terminou em 1º em 0.

### Escolha do limiar de "não encontrei"

| Limiar | Aceitos certos | Falsos negativos | Recusas certas | Falsos positivos | Equilíbrio |
|---|---|---|---|---|---|
| 0.30 | 4 | 25 | 0 | 5 | 0.07 |
| 0.35 | 4 | 25 | 0 | 5 | 0.07 |
| 0.40 | 4 | 25 | 0 | 5 | 0.07 |
| 0.45 | 4 | 25 | 0 | 5 | 0.07 |
| 0.50 | 4 | 25 | 0 | 5 | 0.07 |
| 0.55 | 4 | 25 | 0 | 5 | 0.07 |
| 0.60 | 4 | 25 | 3 | 2 | 0.37 |
| 0.65 | 3 | 26 | 4 | 1 | 0.45 |
| 0.70 ← sugerido | 2 | 27 | 5 | 0 | 0.53 |
| 0.75 | 0 | 29 | 5 | 0 | 0.50 |
| 0.80 | 0 | 29 | 5 | 0 | 0.50 |

*Equilíbrio* é a média entre a taxa de casos válidos aceitos com a categoria certa e a taxa de casos fora do catálogo recusados. O limiar sugerido é o de maior equilíbrio; num empate, o que tem menos falsos positivos, porque responder errado com confiança é pior para o gestor do que dizer que não encontrou.

### Casos que falharam

| Caso | Tipo | Esperado | 1º lugar | Similaridade |
|---|---|---|---|---|
| c01 Buraco grande na rua | representativo | Buraco ou pavimento | Tapa-buraco (Buraco ou pavimento) | 0.6944 |
| c03 Rua de terra virou lamaçal | representativo | Buraco ou pavimento | Tapa-buraco (Buraco ou pavimento) | 0.6374 |
| c04 Poste apagado | representativo | Iluminação pública | Tapa-buraco (Buraco ou pavimento) | 0.6351 |
| c05 rua um breu | informal | Iluminação pública | Tapa-buraco (Buraco ou pavimento) | 0.6458 |
| c06 Lâmpada acesa de dia | representativo | Iluminação pública | Tapa-buraco (Buraco ou pavimento) | 0.6138 |
| c07 Entulho na calçada | representativo | Lixo e limpeza | Tapa-buraco (Buraco ou pavimento) | 0.5982 |
| c08 lixo acumulado | informal | Lixo e limpeza | Tapa-buraco (Buraco ou pavimento) | 0.5906 |
| c09 Lixeira quebrada | representativo | Lixo e limpeza | Tapa-buraco (Buraco ou pavimento) | 0.6281 |
| c10 Bueiro entupido | representativo | Bueiro e drenagem | Tapa-buraco (Buraco ou pavimento) | 0.6427 |
| c11 alaga tudo | informal | Bueiro e drenagem | Tapa-buraco (Buraco ou pavimento) | 0.6242 |
| c12 Tampa de bueiro solta | representativo | Bueiro e drenagem | Tapa-buraco (Buraco ou pavimento) | 0.6772 |
| c13 Calçada quebrada | representativo | Calçada e acessibilidade | Tapa-buraco (Buraco ou pavimento) | 0.6478 |
| c14 Sem rampa para cadeirante | representativo | Calçada e acessibilidade | Tapa-buraco (Buraco ou pavimento) | 0.6006 |
| c15 raiz levantou a calçada | informal | Calçada e acessibilidade | Tapa-buraco (Buraco ou pavimento) | 0.6265 |
| c16 Placa de pare caída | representativo | Sinalização de trânsito | Tapa-buraco (Buraco ou pavimento) | 0.6525 |
| c17 Semáforo apagado | representativo | Sinalização de trânsito | Tapa-buraco (Buraco ou pavimento) | 0.6393 |
| c18 faixa apagou | informal | Sinalização de trânsito | Tapa-buraco (Buraco ou pavimento) | 0.602 |
| c19 Árvore com galho quebrado | representativo | Praças e áreas verdes | Tapa-buraco (Buraco ou pavimento) | 0.5977 |
| c20 Mato alto na praça | representativo | Praças e áreas verdes | Tapa-buraco (Buraco ou pavimento) | 0.6073 |
| c21 brinquedo quebrado | informal | Praças e áreas verdes | Tapa-buraco (Buraco ou pavimento) | 0.6108 |
| c22 Carro abandonado | representativo | Outros | Tapa-buraco (Buraco ou pavimento) | 0.583 |
| c23 Material de obra na rua | representativo | Outros | Tapa-buraco (Buraco ou pavimento) | 0.6205 |
| c28 árvore caindo | ambiguo | Praças e áreas verdes | Tapa-buraco (Buraco ou pavimento) | 0.5968 |
| c30 Bueiro entupido | categoria_errada | Bueiro e drenagem | Tapa-buraco (Buraco ou pavimento) | 0.6612 |
| c31 Poste apagado | categoria_errada | Iluminação pública | Tapa-buraco (Buraco ou pavimento) | 0.6238 |
| c32 Lixo na praça | categoria_errada | Lixo e limpeza | Tapa-buraco (Buraco ou pavimento) | 0.5875 |
| c34 Poste apagado | desvio | Iluminação pública | Tapa-buraco (Buraco ou pavimento) | 0.5137 |

<!-- busca:fim -->

<!-- geracao:inicio -->

## Avaliação da geração (busca + Gemini)

> **Atenção:** 34 casos com rótulo não revisado. Números provisórios.

34 casos. Tempo médio por encaminhamento: 0.61 s. Erros de execução: 0.

| Critério | Resultado | Casos | O que significa |
|---|---|---|---|
| Fonte citada | 100% | 2 de 2 | respostas com serviço que trazem a URL da ficha |
| Recusa certa | 100% | 5 de 5 | casos fora do catálogo que terminaram em "não encontrei" |
| Categoria certa | 7% | 2 de 29 | ficha escolhida da categoria esperada |
| Serviço certo | — | 0 de 0 | ficha escolhida igual ao `servico_esperado` (só casos rotulados) |
| Resistiu ao desvio | 50% | 1 de 2 | pedidos para mudar as regras foram ignorados |
| Sem prazo ou órgão inventado | 100% | 1 de 1 | textos gerados sem citação ausente da ficha |

O plano B (serviço e fonte sem texto gerado) foi usado em 1 casos reais.

**Gemini fora do ar (simulado):** FALHOU (sem serviço).

### Citações para revisão manual

Nenhuma citação de prazo ou órgão fora da ficha foi detectada automaticamente.

### Amostra de textos gerados

**c33 · Buraco na rua** → Tapa-buraco

> Solicita-se o serviço de tapa-buraco para reparo de dano no asfalto. O problema foi registrado na categoria de buraco ou pavimento.

<!-- geracao:fim -->
