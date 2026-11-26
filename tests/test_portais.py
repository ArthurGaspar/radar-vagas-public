"""Adaptadores dos portais de busca, com respostas no formato real das APIs."""

from vagas import rede
from vagas.fontes import getonbrd, himalayas, remotar


def test_getonbrd(monkeypatch):
    resposta = {"data": [{
        "id": "dev-react-acme-remote", "links": {"public_url": "https://www.getonbrd.com/jobs/dev-react-acme-remote"},
        "attributes": {
            "title": "Desarrollador React", "description_headline": "Requirements",
            "description": "<ul><li>React</li></ul>", "desirable_headline": "Nice to have",
            "desirable": "<p>Playwright</p>", "remote_modality": "remote_local", "countries": ["Brazil"],
            "published_at": 1795574203,
            "company": {"data": {"id": "acme", "attributes": {"name": "Acme"}}},
            "seniority": {"data": {"id": "2", "attributes": {"name": "Junior"}}},
            "location_cities": {"data": []},
        }}]}
    monkeypatch.setattr(rede, "get_json", lambda url, **k: resposta)
    v, = getonbrd.buscar("react", {"acme"})
    assert (v.id, v.empresa, v.modelo, v.local, v.nivel_hint) == ("getonbrd:dev-react-acme-remote", "Acme", "remoto", "Brazil", "Junior")
    assert v.estagio_ok and "Nice to have\nPlaywright" in v.descricao


def test_remotar(monkeypatch):
    resposta = {"data": [{
        "id": 173456, "title": "Pessoa Desenvolvedora Typescript", "subtitle": "APIs REST",
        "description": "<p>Time de saúde</p>", "type": "remote", "city": None, "state": None, "country": None,
        "active": True, "expired": False, "companyDisplayName": "FCamara",
        "externalLink": "https://fcamara.gupy.io/job/eyJqb2JJZCI6MTI5Mzg5NTV9",
        "createdAt": "2026-11-25T00:11:10.821-03:00",
        "jobRequirements": [{"description": "PostgreSQL", "mandatory": True}, {"description": "Kafka", "mandatory": False}],
    }, {"id": 2, "title": "Expirada", "active": False}]}
    monkeypatch.setattr(rede, "get_json", lambda url, **k: resposta)
    v, = remotar.buscar("typescript", set())
    assert (v.id, v.modelo, v.local) == ("remotar:173456", "remoto", "Brasil")
    assert v.url.startswith("https://fcamara.gupy.io/job/")
    assert "Requisitos\n- PostgreSQL\nDiferenciais\n- Kafka" in v.descricao


def test_himalayas_junta_as_duas_buscas_sem_repetir(monkeypatch):
    job = {"title": "Full Stack Developer", "companyName": "Acme", "seniority": ["Mid-level", "Entry-level"],
           "locationRestrictions": [], "description": "<p>React</p>", "pubDate": 1795582122,
           "guid": "https://himalayas.app/companies/acme/jobs/full-stack-developer",
           "applicationLink": "https://himalayas.app/companies/acme/jobs/full-stack-developer"}
    monkeypatch.setattr(rede, "get_json", lambda url, **k: {"jobs": [job]})
    v, = himalayas.buscar("full stack", set())
    assert v.id == "himalayas:companies/acme/jobs/full-stack-developer"
    assert (v.local, v.modelo, v.nivel_hint) == ("Worldwide", "remoto", "Entry-level")
