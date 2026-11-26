"""InHire: API pública usada pelas páginas empresa.inhire.app. A empresa é
identificada pelo header X-Tenant (= subdomínio)."""

from . import modelo, nova
from .. import rede
from ..texto import html_para_texto

API = "https://api.inhire.app/job-posts/public/pages"
PAISES = {"BR": "Brasil"}


def listar(empresa):
    dados = rede.get_json(API, headers={"X-Tenant": empresa.slug})
    vagas = []
    for j in dados.get("jobsPage") or []:
        if j.get("status") not in (None, "published"):
            continue
        local = j.get("location") or ""
        vagas.append(nova(
            empresa, j["jobId"],
            titulo=j.get("displayName", ""),
            url=f"https://{empresa.slug}.inhire.app/vagas/{j['jobId']}",
            local=PAISES.get(local, local),
            modelo=modelo(j.get("workplaceType")),
            extra={"job_id": j["jobId"], "slug": empresa.slug},
        ))
    return vagas


def detalhar(vaga):
    j = rede.get_json(f"{API}/{vaga.extra['job_id']}", headers={"X-Tenant": vaga.extra["slug"]})
    vaga.descricao = html_para_texto(j.get("description"))
    vaga.publicada_em = j.get("publishedAt") or vaga.publicada_em
