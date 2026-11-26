import json

import pytest

from vagas import radar
from vagas.dedup import chave_url
from vagas.estado import Estado
from vagas.modelos import Vaga


@pytest.mark.parametrize("a, b", [
    # Remotar repostando Gupy (link base64) x vaga vinda da própria Gupy
    ("https://fcamara.gupy.io/job/eyJqb2JJZCI6MTI5Mzg5NTUsInNvdXJjZSI6InJlbW90YXIifQ==?jobBoardSource=remotar",
     "https://fcamara.gupy.io/jobs/12938955"),
    ("https://jobs.ashbyhq.com/Supabase/2184CFBD/application?utm_source=remotar",
     "https://jobs.ashbyhq.com/supabase/2184cfbd"),
    ("https://job-boards.greenhouse.io/vercel/jobs/555?gh_src=x", "https://vercel.com/careers/x?gh_jid=555"),
    ("https://jobs.lever.co/ciandt/abc-123/apply", "https://jobs.lever.co/ciandt/abc-123"),
    ("https://www.getonbrd.com/jobs/x-y/", "https://getonbrd.com/jobs/x-y"),
])
def test_mesma_vaga_mesma_chave(a, b):
    assert chave_url(a) == chave_url(b)


def test_chave_da_gupy_bate_com_id_da_fonte_gupy():
    assert chave_url("https://empresa.gupy.io/jobs/12599589") == "gupy:12599589"


def vaga(id_, url, fonte):
    return Vaga(id=id_, fonte=fonte, ats=fonte.split(":")[0], empresa="X", titulo="Software Engineer",
                url=url, local="Remote - Brazil", modelo="remoto")


def test_executar_nao_notifica_repostagem(tmp_path, monkeypatch):
    estado_json = tmp_path / "vistos.json"
    ashby = "https://jobs.ashbyhq.com/acme/1111"
    # 1ª execução: só registra (fontes novas)
    coletas = [
        {"ashby:acme": [vaga("ashby:acme:1111", ashby, "ashby:acme")], "remotar-busca:x": []},
        # 2ª: a mesma vaga reaparece na Remotar com outro id e link com /application
        {"ashby:acme": [vaga("ashby:acme:1111", ashby, "ashby:acme")],
         "remotar-busca:x": [vaga("remotar:9", ashby + "/application", "remotar-busca:x"),
                             vaga("remotar:10", "https://acme.com/careers", "remotar-busca:x"),
                             vaga("remotar:11", "https://acme.com/careers", "remotar-busca:x")]},
    ]
    enviados = []
    monkeypatch.setattr(radar, "coletar", lambda cfg, paginas=1: (coletas.pop(0), {}))
    monkeypatch.setattr(radar.discord, "enviar", lambda lote, a, m: enviados.extend(lote) or lote)

    from vagas.config import carregar
    cfg = carregar()
    radar.executar(cfg, estado_json)
    assert enviados == []
    radar.executar(cfg, estado_json)
    # remotar:9 é repostagem; 10 e 11 compartilham um link genérico, que não vira chave
    assert sorted(n.vaga.id for n in enviados) == ["remotar:10", "remotar:11"]
    vistos = json.loads(estado_json.read_text())["vistos"]
    assert "url:acme.com/careers" not in vistos


def test_pausa_longa_le_mais_paginas(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from vagas.config import carregar

    estado_json = tmp_path / "vistos.json"
    paginas_usadas = []
    monkeypatch.setattr(radar, "coletar", lambda cfg, paginas=1: paginas_usadas.append(paginas) or ({}, {}))
    monkeypatch.setattr(radar.discord, "enviar", lambda lote, a, m: lote)
    monkeypatch.setattr(radar.discord, "enviar_log", lambda titulo, linhas=None: None)
    cfg = carregar()

    radar.executar(cfg, estado_json)               # sem estado: 1 página
    radar.executar(cfg, estado_json)               # acabou de rodar: 1 página
    # Simula a primeira execução do dia: última às 23h17, agora 6h17 (Brasília).
    manha = _utc("2026-11-25 06:17")
    monkeypatch.setattr(radar, "datetime", type("dt", (), {"now": staticmethod(lambda tz=None: manha)}))
    dados = json.loads(estado_json.read_text())
    dados["ultima_execucao"] = _utc("2026-11-24 23:17").isoformat()
    estado_json.write_text(json.dumps(dados))
    radar.executar(cfg, estado_json)               # depois da madrugada: mais páginas
    assert paginas_usadas == [1, 1, 3]


def _utc(brt: str):
    """'2026-11-25 06:17' em horário de Brasília -> datetime UTC."""
    from datetime import datetime, timedelta, timezone
    return datetime.fromisoformat(brt).replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)


@pytest.mark.parametrize("ultima, agora, tipo", [
    ("2026-11-25 14:17", "2026-11-25 15:17", "normal"),
    ("2026-11-24 23:17", "2026-11-25 06:17", "madrugada"),    # pausa noturna planejada
    ("2026-11-24 23:17", "2026-11-25 07:40", "madrugada"),    # GitHub/PC atrasou, ainda de manhã
    ("2026-11-24 23:17", "2026-11-25 10:05", "inesperada"),   # PC só ligou às 10h
    ("2026-11-24 15:00", "2026-11-25 06:17", "inesperada"),   # desligado desde a tarde
    ("2026-11-25 11:36", "2026-11-25 14:46", "inesperada"),   # PC desligado à tarde
    (None, "2026-11-25 14:46", "normal"),                     # primeira execução
])
def test_classificar_pausa(ultima, agora, tipo):
    assert radar.classificar_pausa(_utc(ultima) if ultima else None, _utc(agora), {}) == tipo


def test_pausa_inesperada_registra_sem_notificar(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from vagas.config import carregar

    estado_json = tmp_path / "vistos.json"
    v1 = vaga("ashby:acme:1", "https://jobs.ashbyhq.com/acme/1", "ashby:acme")
    v2 = vaga("ashby:acme:2", "https://jobs.ashbyhq.com/acme/2", "ashby:acme")
    coletas = [{"ashby:acme": []}, {"ashby:acme": [v1]}, {"ashby:acme": [v1, v2]}]
    enviados, logs = [], []
    monkeypatch.setattr(radar, "coletar", lambda cfg, paginas=1: (coletas.pop(0), {}))
    monkeypatch.setattr(radar.discord, "enviar", lambda lote, a, m: enviados.extend(lote) or lote)
    monkeypatch.setattr(radar.discord, "enviar_log", lambda titulo, linhas=None: logs.append(titulo))
    # Fixa "agora" num horário de tarde, para a pausa nunca cair na janela da manhã.
    tarde = _utc("2026-11-25 15:17")
    monkeypatch.setattr(radar, "datetime", type("dt", (), {"now": staticmethod(lambda tz=None: tarde)}))
    cfg = carregar()

    radar.executar(cfg, estado_json)                       # registra a fonte
    dados = json.loads(estado_json.read_text())
    dados["ultima_execucao"] = (tarde - timedelta(hours=5)).isoformat()
    estado_json.write_text(json.dumps(dados))
    radar.executar(cfg, estado_json)                       # 5h parado à tarde: v1 vira acumulado
    assert enviados == [] and logs and "5.0h" in logs[0]
    radar.executar(cfg, estado_json)                       # agora normal: só v2 é novidade
    assert [n.vaga.id for n in enviados] == ["ashby:acme:2"]
