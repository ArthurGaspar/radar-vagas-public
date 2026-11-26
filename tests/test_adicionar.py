import pytest

from vagas.adicionar import adicionar, identificar
from vagas.config import carregar_empresas


@pytest.mark.parametrize("url, esperado", [
    ("https://job-boards.greenhouse.io/anthropic/jobs/4020305008", ("greenhouse", "anthropic")),
    ("https://boards.greenhouse.io/embed/job_board?for=stripe", ("greenhouse", "stripe")),
    ("https://jobs.lever.co/ciandt/a832b733", ("lever", "ciandt")),
    ("https://jobs.ashbyhq.com/supabase/2184cfbd", ("ashby", "supabase")),
    ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/X_JR1",
     ("workday", "nvidia.wd5/NVIDIAExternalCareerSite")),
    ("https://jobs.smartrecruiters.com/ServiceNow/744000", ("smartrecruiters", "ServiceNow")),
    ("https://jobs.smartrecruiters.com/oneclick-ui/company/ServiceNow/publication/37ba2d8c?dcr_ci=ServiceNow",
     ("smartrecruiters", "ServiceNow")),
    ("https://careers.smartrecruiters.com/BoschGroup", ("smartrecruiters", "BoschGroup")),
    ("https://apply.workable.com/huggingface/j/81B46579FE/", ("workable", "huggingface")),
    ("https://polestar.teamtailor.com/jobs/8746790-adas", ("teamtailor", "polestar")),
    ("https://bunq.recruitee.com/o/compliance", ("recruitee", "bunq")),
    ("https://empresa.gupy.io/jobs/12599589", ("gupy", "empresa")),
    ("lyncas.inhire.app/vagas/889e2725/x", ("inhire", "lyncas")),
])
def test_identificar(url, esperado):
    assert identificar(url) == esperado


@pytest.mark.parametrize("url", [
    "https://apply.workable.com/j/81B46579FE",
    "https://stripe.com/jobs/search?gh_jid=123",
    "https://www.linkedin.com/jobs/view/123",
])
def test_identificar_explica_quando_nao_da(url):
    with pytest.raises(ValueError):
        identificar(url, sondar=False)


def test_dominio_proprio_recruitee(monkeypatch):
    from vagas import rede
    oferta = {"offers": [{"mailbox_email": "job.7lvyv@publitas.recruitee.com"}]}
    monkeypatch.setattr(rede, "get_json", lambda url, **k: oferta)
    assert identificar("https://jobs.publitas.com/o/staff-product-engineer") == ("recruitee", "publitas")


def test_dominio_proprio_teamtailor(monkeypatch):
    from vagas import rede
    def falha(url, **k):
        raise ValueError("404")
    monkeypatch.setattr(rede, "get_json", falha)
    monkeypatch.setattr(rede, "get_texto", lambda url, **k: '<rss xmlns:tt="https://teamtailor.com/locations">')
    assert identificar("https://careers.empresa.com/jobs/1-x") == ("teamtailor", "careers.empresa.com")


def test_adicionar_acrescenta_sem_apagar_comentarios(tmp_path):
    yaml = tmp_path / "empresas.yaml"
    yaml.write_text("# comentário\nempresas:\n  - {nome: A, ats: lever, slug: a}\n", encoding="utf-8")
    msg = adicionar("https://jobs.ashbyhq.com/nova-empresa/1", "Nova & Cia", True, validar=False, caminho=yaml)
    assert msg.startswith("adicionada")
    texto = yaml.read_text(encoding="utf-8")
    assert texto.startswith("# comentário")
    assert "  - {nome: Nova & Cia, ats: ashby, slug: nova-empresa, estagio: true}" in texto
    assert [e.nome for e in carregar_empresas(yaml)] == ["A", "Nova & Cia"]
    assert adicionar("https://jobs.lever.co/a/x", None, False, validar=False, caminho=yaml).startswith("já está")
