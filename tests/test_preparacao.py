from app.preparacao import dividir, limpar


def test_limpar_tira_sobras_de_pagina_e_repeticao():
    bruto = (
        "Ir para o conteúdo\n"
        "Tapa-buraco\n\n"
        "O serviço   repara buracos   em vias públicas da cidade.\n"
        "Compartilhar\n"
        "Facebook\n"
        "O serviço   repara buracos   em vias públicas da cidade.\n"
        "Voltar ao topo"
    )
    limpo = limpar(bruto)
    assert "Ir para o conteúdo" not in limpo
    assert "Compartilhar" not in limpo and "Facebook" not in limpo
    assert limpo.count("repara buracos") == 1
    assert "  " not in limpo


def test_limpar_mantem_separacao_de_paragrafos():
    assert limpar("Primeiro parágrafo.\n\n\n\nSegundo parágrafo.") == "Primeiro parágrafo.\n\nSegundo parágrafo."


def test_texto_curto_vira_um_trecho():
    assert dividir("Uma frase só.") == ["Uma frase só."]


def test_trechos_respeitam_o_tamanho_e_se_sobrepoem():
    frases = [f"Esta é a frase número {i} da ficha de teste." for i in range(60)]
    trechos = dividir(" ".join(frases), tamanho=300, sobreposicao=80)
    assert len(trechos) > 1
    assert all(len(t) <= 300 for t in trechos)
    # o começo de cada trecho repete o final do anterior
    for anterior, seguinte in zip(trechos, trechos[1:]):
        primeira_frase = seguinte.split(". ")[0]
        assert primeira_frase in anterior


def test_frase_gigante_sem_pontuacao_e_cortada():
    trechos = dividir("a" * 2000, tamanho=500, sobreposicao=50)
    assert all(len(t) <= 500 for t in trechos)
    assert len(trechos) >= 4


def test_nada_se_perde_na_divisao():
    frases = [f"Frase {i} com conteúdo." for i in range(40)]
    texto = " ".join(frases)
    juntos = " ".join(dividir(texto, tamanho=200, sobreposicao=40))
    assert all(f in juntos for f in frases)
