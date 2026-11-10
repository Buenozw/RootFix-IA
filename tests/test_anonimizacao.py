from app.anonimizacao import anonimizar, anonimizar_texto
from app.modelos import ProblemaAnonimo


def test_remove_email_telefone_e_cpf():
    texto = ("Falem comigo: maria.souza+teste@gmail.com ou (11) 91234-5678, ou 11 3456-7890. "
             "Meu CPF é 123.456.789-09.")
    limpo = anonimizar_texto(texto)
    assert "@" not in limpo and "91234" not in limpo and "3456-7890" not in limpo and "789-09" not in limpo
    assert limpo.count("[telefone removido]") == 2
    assert "[e-mail removido]" in limpo and "[documento removido]" in limpo


def test_remove_numero_da_casa_mas_mantem_a_rua():
    limpo = anonimizar_texto("O buraco fica na Rua Frei Caneca, 1000 - apto 12, perto da praça.")
    assert "Rua Frei Caneca" in limpo
    assert "1000" not in limpo and "apto 12" not in limpo
    assert "[número removido]" in limpo


def test_nao_estraga_texto_comum():
    texto = "Poste apagado faz 2 semanas, 7 vizinhos reclamaram. Aconteceu em 2026."
    assert anonimizar_texto(texto) == texto


def test_anonimiza_titulo_descricao_e_observacoes():
    problema = ProblemaAnonimo(
        titulo="Liga pra mim 11 98888-7777",
        descricao="Escreve para joao@exemplo.com",
        observacoes=["(11) 97777-6666", "Também vi o buraco"],
    )
    limpo = anonimizar(problema)
    juntos = " ".join([limpo.titulo, limpo.descricao, *limpo.observacoes])
    assert "98888" not in juntos and "joao@" not in juntos and "97777" not in juntos
    assert "Também vi o buraco" in limpo.observacoes
