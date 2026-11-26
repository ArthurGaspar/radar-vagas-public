from vagas.__main__ import demo
from vagas.config import carregar


def test_demo_roda_offline_e_mostra_as_tres_vagas_que_passam(capsys):
    demo(carregar())
    saida = capsys.readouterr().out
    assert "Seriam notificadas (3)" in saida
    assert "nível (senior)" in saida and "nível (estagio)" in saida
    assert "título" in saida and "remoto restrito" in saida
