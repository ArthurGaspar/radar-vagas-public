import requests

from vagas.discord import dividir_mensagens
from vagas.estado import Estado
from vagas.rede import resumir_erro


def http_error(codigo):
    r = requests.Response()
    r.status_code = codigo
    return requests.exceptions.HTTPError(response=r)


def test_resumir_erro():
    retry = requests.exceptions.RetryError("Max retries exceeded ... too many 429 error responses")
    assert resumir_erro(retry).startswith("429")
    assert resumir_erro(http_error(403)) == "HTTP 403: acesso bloqueado (anti-bot)"
    assert resumir_erro(http_error(404)) == "HTTP 404: não encontrado (slug mudou?)"
    assert resumir_erro(requests.exceptions.ConnectTimeout()) == "sem resposta (timeout/conexão)"


def test_alerta_so_depois_de_falhas_seguidas(tmp_path):
    e = Estado(tmp_path / "vistos.json")
    erro = {"Cadence": "429"}
    assert e.registrar_falhas(erro, 3) == {}
    assert e.registrar_falhas(erro, 3) == {}
    assert e.registrar_falhas(erro, 3) == {"Cadence": 3}   # 3ª seguida: avisa
    assert e.registrar_falhas(erro, 3) == {}                # não repete toda hora
    assert e.registrar_falhas({}, 3) == {} and e.falhas == {}  # voltou a funcionar: zera
    assert e.registrar_falhas(erro, 3) == {}


def test_alerta_persiste_entre_execucoes(tmp_path):
    caminho = tmp_path / "vistos.json"
    e = Estado(caminho)
    e.registrar_falhas({"X": "429"}, 3)
    e.registrar_falhas({"X": "429"}, 3)
    e.salvar()
    assert Estado(caminho).registrar_falhas({"X": "429"}, 3) == {"X": 3}


def test_dividir_mensagens_nao_corta_linha():
    linhas = [f"- fonte {i}: " + "x" * 90 for i in range(60)]
    msgs = dividir_mensagens("⚠️ título", linhas)
    assert len(msgs) > 1 and all(len(m) <= 1900 for m in msgs)
    assert "\n".join(msgs) == "⚠️ título\n" + "\n".join(linhas)
