# Coleta das fichas de serviço

A qualidade do Encaminhador depende destas fichas mais do que do código: o modelo só pode responder o que estiver escrito nelas. Por isso o conteúdo vem **copiado das páginas oficiais**, nunca resumido ou completado de memória.

**Meta:** 30 a 50 fichas, pelo menos 3 por categoria. **Prazo sugerido:** quinta, 12/11, para a indexação e a avaliação da busca começarem na sexta.

## Onde procurar

1. Abra o **Quadro de Serviços** (ou **Carta de Serviços**) de uma subprefeitura. Cada item da lista leva a uma página do SP156 ou da própria subprefeitura. **Cada uma dessas páginas é uma ficha.**
   - [Quadro de Serviços da Subprefeitura Sé](https://prefeitura.sp.gov.br/web/se/w/quadro-de-servi%C3%A7os/se) — cobre a comunidade de teste **Bela Vista**.
   - Quadro ou Carta de Serviços da **Subprefeitura Mooca** — cobre a comunidade de teste **Mooca**.
   - Outras subprefeituras completam o que faltar (ex.: [Carta de Serviços da Vila Prudente](https://prefeitura.sp.gov.br/web/vila_prudente/w/carta-de-servi%C3%A7os), [Zeladoria Urbana de Sapopemba](https://prefeitura.sp.gov.br/web/sapopemba/w/zeladoria_urbana/116576)).
2. Páginas de "como solicitar" das subprefeituras costumam ter mais detalhe (órgão, o que informar). Exemplo usado no arquivo de exemplo: [Tapa-buraco no Ipiranga](https://prefeitura.sp.gov.br/web/ipiranga/w/opera%C3%A7%C3%A3o-tapa-buraco-no-ipiranga-saiba-como-solicitar-o-servi%C3%A7o).
3. Registros de serviço do 156 no GeoSampa servem para conferir o nome oficial do serviço (ex.: [Manutenção de placas de trânsito](https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/api/records/cf2f8943-e76f-482d-83e6-3b765516f490)).

## O que procurar em cada categoria

| Categoria no RootFix | Serviços para procurar | Meta |
|---|---|---|
| Buraco ou pavimento | Tapa-buraco, pavimentação de rua não asfaltada, reparo de guia | 3+ |
| Iluminação pública | Lâmpada apagada ou acesa de dia, poste danificado | 3+ |
| Lixo e limpeza | Lixo e limpeza de via, entulho, lixeira, limpeza de córrego | 3+ |
| Bueiro e drenagem | Limpeza de boca de lobo, galeria, alagamento | 3+ |
| Calçada e acessibilidade | Calçada irregular, rampa de acessibilidade, regras de quem conserta a calçada | 3+ |
| Sinalização de trânsito | Placas, semáforo, faixa de pedestre apagada | 3+ |
| Praças e áreas verdes | Árvore (poda, remoção, risco de queda), manutenção de praça | 3+ |
| Outros | Serviços de zeladoria fora das 7 acima (ex.: veículo abandonado, material de construção na via) | 3+ |

As fichas de "Outros" importam: são elas que ensinam a busca a não forçar tudo para as 7 categorias principais.

## Como preencher

1. Copie `data/raw/_MODELO.md` e dê um nome curto: `servico-subprefeitura.md` (ex.: `tapa-buraco-se.md`).
2. Preencha o cabeçalho com o que **está na página**. Se a página não traz prazo, órgão ou documentos, deixe o campo vazio.
3. Em `termos_populares`, escreva 2 a 4 jeitos que um morador falaria do problema ("poste apagado", "rua um breu"). Esse é o único campo escrito por vocês, e ajuda a busca a entender linguagem informal.
4. Cole o texto da página abaixo do cabeçalho. Tire menus, rodapé e botões.
5. Rode o validador:

   ```bash
   python scripts/validar_fichas.py
   ```

   Ele aponta erro por arquivo e mostra quantas fichas faltam por categoria.

## Divisão sugerida (5 pessoas)

Cada integrante fica com uma ou duas categorias e coleta 6 a 10 fichas. Quem terminar primeiro revisa as fichas de outra pessoa com o validador aberto.
