"""Formatos de entrada e saída do serviço (o que o app manda e recebe) e o que o Gemini devolve."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    """O app (JavaScript) usa camelCase; o código Python usa snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProblemaAnonimo(_Camel):
    """Dados do problema que podem ir para o Gemini: sem nomes, e-mails, telefones ou endereços."""

    titulo: str
    descricao: str
    categoria: str | None = None
    gravidade: str | None = None
    total_apoios: int = 0
    comunidade: str | None = None
    observacoes: list[str] = Field(default_factory=list)


class SimularRequest(_Camel):
    titulo: str = Field(min_length=3, max_length=120)
    descricao: str = Field(min_length=3, max_length=1000)
    categoria: str | None = Field(default=None, max_length=60)
    gravidade: str | None = Field(default=None, max_length=10)
    total_apoios: int = Field(default=0, ge=0)
    comunidade: str | None = Field(default=None, max_length=120)
    observacoes: list[str] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "titulo": "Poste apagado",
                "descricao": "O poste em frente ao número 230 está apagado há duas semanas.",
                "categoria": "Iluminação pública",
                "gravidade": "MEDIA",
                "totalApoios": 7,
                "comunidade": "Bela Vista - Av. Paulista",
                "observacoes": ["À noite a rua fica um breu", "Já liguei e não resolveram"],
            }
        },
    )


class Fonte(_Camel):
    servico: str
    url: str
    data_coleta: str


class Encaminhamento(_Camel):
    problema_id: int | None = None
    encontrado: bool
    servico: str | None = None
    categoria: str | None = None
    orgao: str | None = None
    canal: str | None = None
    prazo_referencia: str | None = None
    documentos_necessarios: str | None = None
    texto_solicitacao: str | None = None
    resumo_observacoes: str | None = None
    motivo_escolha: str | None = None
    fontes: list[Fonte] = Field(default_factory=list)
    texto_gerado: bool = False
    aviso: str


class RespostaLLM(BaseModel):
    """Formato que o Gemini é obrigado a seguir (saída estruturada em JSON)."""

    ficha_escolhida: str | None = Field(
        description="Código da ficha que resolve o problema (ex.: F1), ou null se nenhuma resolve."
    )
    motivo: str = Field(description="Uma frase dizendo por que essa ficha resolve, ou por que nenhuma resolve.")
    texto_solicitacao: str | None = Field(
        description="Texto formal e curto da solicitação para o SP156, ou null se nenhuma ficha resolve."
    )
    resumo_observacoes: str | None = Field(
        description="Até 3 frases com os fatos relatados pelos vizinhos, ou null se não houver observações."
    )
