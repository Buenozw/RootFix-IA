# Contrato com o app (mobile)

Tudo que o app RootFix precisa para usar o Encaminhador do gestor.

## Onde

- **Endereço:** `https://<nome-do-serviço>.onrender.com` (definido no deploy; ver [deploy.md](deploy.md)).
- **Documentação interativa:** `/docs` no mesmo endereço.

## Quando mostrar o botão "Encaminhar com IA"

Na tela de um problema, só quando a resposta do `GET /problemas/{id}` da API Java tiver:

```json
"adotado": true,
"souGestor": true
```

Para morador, ou para problema ainda não adotado, o botão não aparece. Se aparecer por engano, o serviço responde 403 ou 409 de qualquer jeito.

## Pedido

```
POST /encaminhar/{problemaId}
Authorization: Bearer <o mesmo token JWT que o app usa na API Java>
```

Sem corpo. O serviço lê o problema e as observações na API Java com esse token.

Exemplo em React Native:

```js
const URL_IA = "https://<nome-do-serviço>.onrender.com";

export async function encaminharComIA(problemaId, token) {
  const controle = new AbortController();
  const limite = setTimeout(() => controle.abort(), 120000); // até 2 min: as duas APIs podem estar acordando
  try {
    const resposta = await fetch(`${URL_IA}/encaminhar/${problemaId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      signal: controle.signal,
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.detail || "Não foi possível encaminhar agora.");
    return corpo;
  } finally {
    clearTimeout(limite);
  }
}
```

## Tempo de resposta

- Normal: **10 a 20 segundos** (leitura na API Java, busca nas fichas e geração do texto).
- Se o serviço ou a API Java estiverem dormindo no Render: **até 1 a 2 minutos** na primeira chamada.

Mostre um carregamento com uma frase, por exemplo "Procurando o serviço da prefeitura e escrevendo a solicitação…", e não deixe o gestor tocar no botão duas vezes.

## Resposta de sucesso (200)

O 200 tem três formas. O app decide o que mostrar pelos campos `encontrado` e `textoGerado`.

| Campo | Tipo | O que é |
|---|---|---|
| `problemaId` | número | Id do problema |
| `encontrado` | booleano | `true` se achou um serviço da prefeitura para o problema |
| `servico` | texto ou null | Nome do serviço, ex.: "Tapa-buraco" |
| `categoria` | texto ou null | Categoria da ficha usada |
| `orgao` | texto ou null | Órgão responsável, quando a ficha informa |
| `canal` | texto ou null | Como pedir: app SP156, portal, telefone… |
| `prazoReferencia` | texto ou null | Prazo, quando a ficha informa |
| `documentosNecessarios` | texto ou null | O que informar ao pedir, separado por `;` |
| `textoSolicitacao` | texto ou null | Texto pronto para colar no SP156 |
| `resumoObservacoes` | texto ou null | Resumo do que os vizinhos relataram |
| `motivoEscolha` | texto ou null | Por que esse serviço (ou por que nenhum) |
| `fontes` | lista | `[{ "servico", "url", "dataColeta" }]`: a página oficial usada |
| `textoGerado` | booleano | `false` quando o texto não pôde ser gerado agora |
| `aviso` | texto | Sempre presente; mostrar ao gestor |

### 1. Encontrou e escreveu (`encontrado: true`, `textoGerado: true`)

```json
{
  "problemaId": 2,
  "encontrado": true,
  "servico": "Tapa-buraco",
  "categoria": "Buraco ou pavimento",
  "orgao": "…",
  "canal": "Aplicativo SP156, Portal SP156 ou WhatsApp",
  "prazoReferencia": null,
  "documentosNecessarios": "Endereço completo com ponto de referência; Foto nítida do trecho danificado",
  "textoSolicitacao": "Solicitamos o reparo de um buraco de grande porte…",
  "resumoObservacoes": "Moradores relatam que o buraco está assim há uma semana…",
  "motivoEscolha": "A ficha trata de reparo de buracos em vias públicas.",
  "fontes": [{ "servico": "Tapa-buraco", "url": "https://prefeitura.sp.gov.br/…", "dataColeta": "2026-11-12" }],
  "textoGerado": true,
  "aviso": "Revise antes de enviar. Prazos são referência da fonte consultada…"
}
```

Mostrar: serviço, órgão e canal; o texto com um botão **Copiar**; o resumo das observações; o link da fonte (abre no navegador); o aviso.

### 2. Encontrou, mas sem texto (`encontrado: true`, `textoGerado: false`)

Aconteceu quando a IA que escreve o texto ficou fora do ar. Vêm serviço, canal e fonte; `textoSolicitacao` vem `null`. Mostrar o que veio, o aviso, e um botão **Tentar de novo**. O `orgao` pode vir `null` de propósito quando a ficha é de outra região: o aviso explica.

### 3. Não encontrou (`encontrado: false`)

O problema não combina com nenhuma ficha de serviço da base (não é de zeladoria, ou a ficha da região ainda não foi coletada). Mostrar o `motivoEscolha`, se vier, e o aviso. Não é erro: não precisa de "tentar de novo".

## Erros

Todo erro vem como `{ "detail": "mensagem" }`, já escrita para mostrar ao usuário.

| Código | Quando | O que o app faz |
|---|---|---|
| 401 | Token ausente, inválido ou expirado | Mandar para o login |
| 403 | Quem pediu não é o gestor da comunidade | Mostrar a mensagem |
| 404 | Problema não existe | Mostrar a mensagem e voltar |
| 409 | Problema ainda não adotado | Mostrar "Adote o problema antes de encaminhar" |
| 422 | Id inválido | Erro de programação no app |
| 502 | API Java fora do ar ou com erro | Mostrar a mensagem e oferecer "Tentar de novo" |
| 503 | Base de fichas ausente ou busca indisponível | Mostrar a mensagem e oferecer "Tentar de novo" mais tarde |
| 504 | API Java demorou demais (acordando no Render) | Mostrar a mensagem e oferecer "Tentar de novo" em 1 minuto |

## O que o serviço não faz

- Não protocola nada no SP156: o gestor revisa o texto e envia.
- Não guarda o problema, o texto nem o token.
- Não muda o status do problema: isso continua no painel .NET.
