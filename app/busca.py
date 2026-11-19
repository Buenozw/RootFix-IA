"""Busca, na base vetorial, as fichas de serviço que combinam com um problema relatado.

Passos:
1. Junta título e descrição do problema num texto só e gera o vetor dele.
2. Busca na base toda e agrupa os trechos por serviço, ordenando pela melhor similaridade.
3. Se o problema tem uma categoria útil (vinda do Spring AI), busca também só nessa categoria e
   garante que a melhor ficha dela esteja entre as fichas enviadas ao Gemini. A categoria é uma
   preferência, não uma restrição: se o Spring AI errou, a ficha certa de outra categoria continua
   na lista (plano B da categoria).
4. Se nem o melhor serviço passar do limiar, responde que não encontrou, para o LLM não inventar.

Por que não filtrar: a avaliação de 18/11 mostrou que, com a escala comprimida do
gemini-embedding-001, a ficha da categoria errada ainda pontua de 0,65 a 0,70. Uma busca só na
categoria nunca parecia "fraca", então a busca na base toda nunca era acionada (0 de 3 casos), e o
Gemini recebia só fichas da categoria errada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import config
from app.embeddings import Embedder
from app.fichas import CATEGORIAS

SEM_FILTRO = {None, "", "Outros"}
TRECHOS_POR_CONSULTA = 12  # trechos lidos da base antes de agrupar por serviço
VAGAS_NO_PROMPT = 3  # quantas fichas o Gemini recebe (FICHAS_NO_PROMPT em gerador.py)


@dataclass
class Trecho:
    texto: str
    similaridade: float
    meta: dict


@dataclass
class Candidato:
    servico: str
    categoria: str
    similaridade: float  # a do melhor trecho desse serviço
    meta: dict  # metadados do melhor trecho (órgão, canal, prazo, URL…)
    trechos: list[Trecho] = field(default_factory=list)


@dataclass
class ResultadoBusca:
    encontrado: bool
    candidatos: list[Candidato]
    filtro_usado: str | None  # categoria preferida (a do Spring AI), ou None quando não havia categoria útil
    caiu_no_plano_b: bool  # True quando a melhor ficha veio de outra categoria que não a preferida
    limiar: float

    @property
    def melhor(self) -> Candidato | None:
        return self.candidatos[0] if self.candidatos else None


class BaseIncompativel(RuntimeError):
    """A base foi criada com outro modelo de embeddings: os vetores não se comparam."""


def conferir_assinatura(colecao, esperada: str) -> None:
    criada_com = (colecao.metadata or {}).get("embeddings")
    if criada_com != esperada:
        raise BaseIncompativel(
            f"A base foi criada com '{criada_com}', mas a busca está usando '{esperada}'. "
            "Rode python scripts/indexar.py de novo ou ajuste EMBEDDINGS_PROVEDOR no .env."
        )


def texto_da_consulta(titulo: str, descricao: str) -> str:
    return f"{(titulo or '').strip()}. {(descricao or '').strip()}".strip(". ")


class Buscador:
    def __init__(self, embedder: Embedder, colecao=None, limiar: float | None = None,
                 assinatura_esperada: str | None = None):
        self.embedder = embedder
        self.assinatura_esperada = assinatura_esperada
        if colecao is not None and assinatura_esperada:
            conferir_assinatura(colecao, assinatura_esperada)
        self._colecao = colecao
        self.limiar = config.limiar_similaridade if limiar is None else limiar

    @property
    def colecao(self):
        if self._colecao is None:
            import chromadb

            cliente = chromadb.PersistentClient(path=str(config.pasta_vetores))
            colecao = cliente.get_collection(config.nome_colecao)
            if self.assinatura_esperada:
                conferir_assinatura(colecao, self.assinatura_esperada)
            self._colecao = colecao
        return self._colecao

    def _consultar(self, vetor: list[float], categoria: str | None) -> list[Trecho]:
        total = self.colecao.count()
        if total == 0:
            return []
        filtro = {"categoria": categoria} if categoria else None
        resposta = self.colecao.query(
            query_embeddings=[vetor],
            n_results=min(TRECHOS_POR_CONSULTA, total),
            where=filtro,
            include=["documents", "metadatas", "distances"],
        )
        trechos = []
        for texto, meta, distancia in zip(resposta["documents"][0], resposta["metadatas"][0], resposta["distances"][0]):
            # A base usa distância de cosseno (0 = igual). Similaridade = 1 - distância.
            trechos.append(Trecho(texto=texto, similaridade=round(1 - distancia, 4), meta=meta))
        return trechos

    @staticmethod
    def _agrupar(trechos: list[Trecho]) -> list[Candidato]:
        por_servico: dict[str, Candidato] = {}
        for trecho in sorted(trechos, key=lambda t: t.similaridade, reverse=True):
            chave = trecho.meta.get("arquivo") or trecho.meta.get("servico")
            if chave not in por_servico:
                por_servico[chave] = Candidato(
                    servico=trecho.meta.get("servico", ""),
                    categoria=trecho.meta.get("categoria", ""),
                    similaridade=trecho.similaridade,
                    meta=trecho.meta,
                )
            por_servico[chave].trechos.append(trecho)
        return sorted(por_servico.values(), key=lambda c: c.similaridade, reverse=True)

    @staticmethod
    def _mesclar(da_categoria: list[Candidato], base_toda: list[Candidato],
                 vagas: int = VAGAS_NO_PROMPT) -> list[Candidato]:
        """Junta as duas listas sem repetir serviço, em ordem de similaridade, e garante que a melhor
        ficha da categoria preferida esteja entre as `vagas` primeiras (as que vão para o Gemini)."""
        def chave(c: Candidato) -> str:
            return c.meta.get("arquivo") or c.servico

        # Um serviço da categoria preferida aparece nas duas buscas com a mesma similaridade; fica a
        # versão da busca na categoria, que traz mais trechos daquela ficha.
        vistos: dict[str, Candidato] = {}
        for c in da_categoria + base_toda:
            vistos.setdefault(chave(c), c)
        candidatos = sorted(vistos.values(), key=lambda c: c.similaridade, reverse=True)
        if da_categoria:
            posicao = candidatos.index(vistos[chave(da_categoria[0])])
            if posicao >= vagas:
                candidatos.insert(vagas - 1, candidatos.pop(posicao))
        return candidatos

    def buscar(self, titulo: str, descricao: str, categoria: str | None = None,
               usar_filtro: bool = True) -> ResultadoBusca:
        """`usar_filtro=False` ignora a categoria do Spring AI (a avaliação compara as duas formas)."""
        vetor = self.embedder([texto_da_consulta(titulo, descricao)])[0]

        preferida = categoria if usar_filtro and categoria in CATEGORIAS and categoria not in SEM_FILTRO else None
        candidatos = self._agrupar(self._consultar(vetor, None))
        if preferida:
            candidatos = self._mesclar(self._agrupar(self._consultar(vetor, preferida)), candidatos)

        caiu_no_plano_b = bool(preferida and candidatos and candidatos[0].categoria != preferida)
        encontrado = bool(candidatos) and candidatos[0].similaridade >= self.limiar
        return ResultadoBusca(
            encontrado=encontrado,
            candidatos=candidatos,
            filtro_usado=preferida,
            caiu_no_plano_b=caiu_no_plano_b,
            limiar=self.limiar,
        )
