from . import nova
from .. import rede
from ..texto import html_para_texto


def _url(slug):
    # Slug é o subdomínio (empresa.recruitee.com) ou um domínio próprio (jobs.empresa.com).
    return f"https://{slug}/api/offers/" if "." in slug else f"https://{slug}.recruitee.com/api/offers/"


def listar(empresa):
    dados = rede.get_json(_url(empresa.slug))
    vagas = []
    for j in dados.get("offers", []):
        if j.get("status") not in (None, "published"):
            continue
        if j.get("remote"):
            modelo_trab = "remoto"
        elif j.get("hybrid"):
            modelo_trab = "hibrido"
        elif j.get("on_site"):
            modelo_trab = "presencial"
        else:
            modelo_trab = None
        descricao = html_para_texto(j.get("description"))
        if j.get("requirements"):
            descricao += "\nRequirements\n" + html_para_texto(j["requirements"])
        vagas.append(nova(
            empresa, j["id"],
            titulo=j.get("title", ""),
            url=j.get("careers_url", ""),
            local=j.get("location", ""),
            cidade=j.get("city", ""),
            modelo=modelo_trab,
            publicada_em=j.get("published_at"),
            descricao=descricao,
            nivel_hint=j.get("experience_code"),
        ))
    return vagas
