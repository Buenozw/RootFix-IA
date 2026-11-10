from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_health_responde_ok():
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ok"
    assert isinstance(corpo["trechosNaBase"], int)


def test_health_nunca_mostra_a_chave_do_gemini():
    texto = cliente.get("/health").text.lower()
    assert "api_key" not in texto
    assert "apikey" not in texto
