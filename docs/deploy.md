# Deploy no Render

O serviço roda no plano gratuito do Render, no mesmo esquema da API Java: dorme depois de 15 minutos sem uso e leva cerca de 1 minuto para acordar.

## Antes de subir

1. **Base indexada e no Git.** Rode `python scripts/indexar.py` com as fichas finais e faça commit de `data/vetores/` e `data/processado/`. O Render usa essa base pronta e não chama a API de embeddings no build.
2. **Limiar definido.** Rode `python scripts/avaliar_busca.py` e anote o limiar sugerido; ele vai na variável `LIMIAR_SIMILARIDADE`.
3. **Workspace certo.** O plano gratuito dá 750 horas por mês por workspace, e a API Java já usa as horas de um. Este serviço precisa ficar em **outro workspace ou outra conta** do Render (por exemplo, a conta dona do repositório `Buenozw/RootFix-IA`).

## Subindo

1. No Render, clique em **New → Blueprint** e escolha o repositório `RootFix-IA`. O Render lê o `render.yaml` e cria o serviço `rootfix-ia`.
2. Ele vai pedir os valores marcados como secretos:
   - `GEMINI_API_KEY`: a chave do Gemini deste serviço (não a da API Java);
   - `LIMIAR_SIMILARIDADE`: o limiar da avaliação da busca.
3. Confirme. O primeiro build leva alguns minutos.

Se preferir sem Blueprint: **New → Web Service**, mesmo repositório, *Build Command* `pip install -r requirements.txt`, *Start Command* `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, *Health Check Path* `/health`, e as variáveis do `render.yaml` cadastradas à mão.

## Conferindo

Abra `https://<nome-do-serviço>.onrender.com/health`. O deploy está certo quando aparecer:

```json
"baseIndexada": true,
"baseCompativel": true,
"geminiConfigurado": true
```

Depois teste o encaminhamento de verdade apontando o script para o endereço do Render:

```bash
python scripts/testar_integracao.py --problema <id> --servico https://<nome-do-serviço>.onrender.com
```

## Versão do Python

O arquivo `.python-version` fixa o Python em 3.13, a versão em que as dependências foram instaladas e testadas. Sem ele, o Render usaria o padrão de serviços novos, o 3.14.

## Memória

Com os embeddings pelo Gemini, o serviço chegou a 111 MB de pico na medição (`scripts/medir_memoria.py`), contra o limite de 512 MB do plano gratuito. O modelo local (`EMBEDDINGS_PROVEDOR=local`) passa do limite e não deve ser usado no Render.

## Atualizando fichas depois do deploy

Rode `scripts/indexar.py` na máquina, faça commit de `data/vetores/` e `data/processado/` e dê push. Com `autoDeploy`, o Render publica sozinho.
