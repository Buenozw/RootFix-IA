"""Busca, na base vetorial, as fichas de serviço que combinam com um problema relatado.

Passos:
1. Junta título e descrição do problema num texto só e gera o vetor dele.
2. Se o problema tem uma categoria útil (vinda do Spring AI), busca só nos trechos dessa categoria.
3. Se a busca filtrada vier fraca (abaixo do limiar) ou vazia, busca na base toda. Isso cobre o
   caso de o Spring AI ter errado a categoria.
4. Agrupa os trechos por serviço e ordena os serviços pela melhor similaridade.
5. Se nem o melhor serviço passar do limiar, responde que não encontrou, para o LLM não inventar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import config
from app.embeddings import Embedder
from app.fichas import CATEGORIAS

SEM_FILTRO = {None, "", "Outros"}
TRECHOS_POR_CONSULTA = 12  # trechos lidos da base antes de agrupar por serviço


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
    filtro_usado: str | None  # categoria usada no filtro, ou None se buscou na base toda
    caiu_no_plano_b: bool  # True quando a busca filtrada foi fraca e buscou na base toda
    limiar: float

    @property
    def melhor(self) -> Candidato | None:
        return self.candidatos[0] if self.candidatos else None


def texto_da_consulta(titulo: str, descricao: str) -> str:
    return f"{(titulo or '').strip()}. {(descricao or '').strip()}".strip(". ")


class Buscador:
    def __init__(self, embedder: Embedder, colecao=None, limiar: float | None = None):
        self.embedder = embedder
        self._colecao = colecao
        self.limiar = config.limiar_similaridade if limiar is None else limiar

    @property
    def colecao(self):
        if self._colecao is None:
            import chromadb

            cliente = chromadb.PersistentClient(path=str(config.pasta_vetores))
            self._colecao = cliente.get_collection(config.nome_colecao)
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

    def buscar(self, titulo: str, descricao: str, categoria: str | None = None,
               usar_filtro: bool = True) -> ResultadoBusca:
        vetor = self.embedder([texto_da_consulta(titulo, descricao)])[0]

        filtro = categoria if usar_filtro and categoria in CATEGORIAS and categoria not in SEM_FILTRO else None
        caiu_no_plano_b = False
        trechos = self._consultar(vetor, filtro)
        candidatos = self._agrupar(trechos)

        if filtro and (not candidatos or candidatos[0].similaridade < self.limiar):
            caiu_no_plano_b = True
            candidatos = self._agrupar(self._consultar(vetor, None))
            filtro = None

        encontrado = bool(candidatos) and candidatos[0].similaridade >= self.limiar
        return ResultadoBusca(
            encontrado=encontrado,
            candidatos=candidatos,
            filtro_usado=filtro,
            caiu_no_plano_b=caiu_no_plano_b,
            limiar=self.limiar,
        )
