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
5. **Embeddings.** Cada trecho vira um vetor de 768 posições com o `gemini-embedding-001`, pela API do Gemini, com a tarefa `RETRIEVAL_DOCUMENT`. O texto do problema, na hora da busca, usa a tarefa `RETRIEVAL_QUERY`. Os vetores são normalizados para a similaridade de cosseno.
6. **Base vetorial.** Os vetores vão para o Chroma, gravado em disco, com similaridade de cosseno. A base guarda qual modelo a criou (ex.: `gemini:gemini-embedding-001:768`), e a busca se recusa a usar uma base feita com outro modelo, porque vetores de modelos diferentes não se comparam. Cada trecho guarda como metadados o serviço, a categoria, o órgão, o canal, o prazo, os documentos, a URL e a data de coleta. A busca usa a categoria para filtrar e o resto para montar a resposta e citar a fonte.

`data/processado/fichas.jsonl` guarda o texto já limpo de cada ficha, uma por linha, para conferência.

A base (`data/vetores/`) é criada uma vez na máquina do grupo e vai para o repositório. Assim o deploy não chama a API de embeddings a cada build, e cada pedido do app faz só uma chamada (o texto do problema). Sempre que uma ficha mudar, é preciso rodar `scripts/indexar.py` de novo e fazer commit da base.

## Por que essas escolhas

- **Embeddings do Gemini em vez de um modelo local.** O primeiro plano era um modelo local e multilíngue (`paraphrase-multilingual-MiniLM-L12-v2` pelo fastembed). Medido com `scripts/medir_memoria.py`, ele chegou a um pico de **773 MB**, acima dos 512 MB do plano gratuito do Render: só a tabela do vocabulário multilíngue, com cerca de 250 mil palavras, ocupa uns 370 MB. Com o `gemini-embedding-001` os vetores são gerados na API e o serviço cabe no Render. É o mesmo provedor que o RootFix já usa no Java e na geração, e ele é multilíngue (mais de 100 idiomas).
- **O custo dessa troca.** A busca passa a depender da API do Gemini e da cota gratuita: se a API cair, o serviço inteiro fica indisponível, e não só o texto gerado. O texto do problema (já anonimizado) vai para o Google na busca e na geração. O modelo local continua disponível com `EMBEDDINGS_PROVEDOR=local` e `requirements-local.txt`, para rodar na máquina e comparar os dois na avaliação.
- **768 dimensões.** O modelo gera 3072 por padrão, mas aceita vetores menores. 768 está entre os tamanhos que o Google recomenda e deixa a base leve.
- **Chroma.** Guarda vetores e metadados juntos e filtra por categoria na mesma consulta. Para algumas centenas de trechos, não precisa de servidor.

## Memória

`python scripts/medir_memoria.py` prepara o provedor de embeddings e o Chroma e mostra o pico de memória e a folga para os 512 MB do Render.

| Provedor | Pico de memória | Cabe no Render? |
|---|---|---|
| Local (`paraphrase-multilingual-MiniLM-L12-v2`) | 773 MB (Windows, medido em 10/11) | Não |
| Gemini (`gemini-embedding-001`, 768 dimensões) | 111 MB (Windows, medido em 10/11) | Sim, com folga de 401 MB |
