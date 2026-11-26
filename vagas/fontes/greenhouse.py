from . import modelo, nova
from .. import rede
from ..texto import html_para_texto

API = "https://boards-api.greenhouse.io/v1/boards"


def listar(empresa):
    dados = rede.get_json(f"{API}/{empresa.slug}/jobs")
    vagas = []
    for j in dados.get("jobs", []):
        local = (j.get("location") or {}).get("name", "")
        vagas.append(nova(
            empresa, j["id"],
            titulo=j.get("title", ""),
            url=j.get("absolute_url", ""),
            local=local,
            modelo=modelo(local) if "remot" in local.lower() else None,
            publicada_em=j.get("first_published") or j.get("updated_at"),
            extra={"job_id": j["id"], "slug": empresa.slug},
        ))
    return vagas


def detalhar(vaga):
    j = rede.get_json(f"{API}/{vaga.extra['slug']}/jobs/{vaga.extra['job_id']}")
    vaga.descricao = html_para_texto(j.get("content"))
