# Dados: fontes e preparação

## Fontes

As fichas de serviço vêm de páginas públicas da Prefeitura de São Paulo: o Quadro ou Carta de Serviços das subprefeituras, as páginas do SP156 ligadas a eles e páginas de "como solicitar" das subprefeituras. Cada ficha guarda a URL de origem e a data em que foi copiada. O passo a passo da coleta está em [coleta-de-fichas.md](coleta-de-fichas.md).

> A tabela com cada ficha, a URL e a data de coleta entra aqui quando a coleta terminar.

## Preparação

O script `scripts/indexar.py` faz o caminho `data/raw/` → `data/processado/fichas.jsonl` → `data/vetores/`. Rodar de novo apaga a base e cria do zero.

1. **Validação.** Cada ficha passa pelas mesmas regras do `scripts/validar_fichas.py` (campos obrigatórios, categoria igual às 8 da API Java, URL e data válidas, sem texto do modelo esquecido). Ficha com erro é listada e fica de fora, sem derrubar o script. O modelo (`_MODELO.md`) e o exemplo (`exemplo: true`) são pulados.
2. **Limpeza.** Tira sobras de página que vêm junto quando se copia do portal (menus, "Compartilhar", redes sociais, "Voltar ao topo"), espaços repetidos e parágrafos copiados duas vezes. Mantém a separação de parágrafos.
3. **Divisão em trechos.** Frases são juntadas até cerca de 800 caracteres, e cada trecho começa repetindo até 150 caracteres do final do anterior. O tamanho cabe com folga no modelo de embeddings, e a sobreposição evita que uma instrução fique cortada entre dois trechos.
4. **Cabeçalho de busca.** Cada trecho recebe no início uma linha com o serviço, a categoria e os termos populares da ficha ("Serviço: Tapa-buraco. Categoria: Buraco ou pavimento. Também chamado de: buraco na rua; cratera."). Sem isso, um trecho genérico do meio da ficha, como "informe o endereço e envie uma foto", não diria de que serviço fala e apareceria para qualquer problema.
5. **Embeddings.** Cada trecho vira um vetor com o modelo `paraphrase-multilingual-MiniLM-L12-v2`, que roda localmente pelo fastembed (ONNX, sem PyTorch) e entende português.
6. **Base vetorial.** Os vetores vão para o Chroma, gravado em disco, com similaridade de cosseno. Cada trecho guarda como metadados o serviço, a categoria, o órgão, o canal, o prazo, os documentos, a URL e a data de coleta. A busca usa a categoria para filtrar e o resto para montar a resposta e citar a fonte.

`data/processado/fichas.jsonl` guarda o texto já limpo de cada ficha, uma por linha, para conferência.

## Por que essas escolhas

- **Embeddings locais em vez de API:** gerar vetores é a parte que mais se repete (a base inteira em cada indexação e cada busca). Rodando local, não gasta a cota gratuita do Gemini e não manda o texto dos problemas para mais um serviço externo.
- **Modelo multilíngue pequeno:** os moradores escrevem em português informal. O modelo tem cerca de 220 MB, o que cabe no plano gratuito do Render. Modelos multilíngues maiores, como o `multilingual-e5-large` (2,2 GB), não caberiam.
- **Chroma:** guarda vetores e metadados juntos e filtra por categoria na mesma consulta. Para algumas centenas de trechos, não precisa de servidor.

## Memória

`python scripts/medir_memoria.py` carrega o modelo e o Chroma e mostra o pico de memória e a folga para os 512 MB do Render.

> Resultado da medição: _a preencher depois de rodar na máquina do grupo._
