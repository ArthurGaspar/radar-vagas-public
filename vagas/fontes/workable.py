from . import nova
from .. import rede
from ..texto import html_para_texto


def listar(empresa):
    dados = rede.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{empresa.slug}?details=true")
    vagas = []
    for j in dados.get("jobs", []):
        locais = [", ".join(filter(None, [l.get("city"), l.get("region"), l.get("country")])) for l in j.get("locations") or []]
        if not locais:
            locais = [", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country")]))]
        vagas.append(nova(
            empresa, j["shortcode"],
            titulo=j.get("title", ""),
            url=j.get("url") or j.get("shortlink", ""),
            local=" / ".join(filter(None, locais)),
            cidade=j.get("city", "") if len(locais) == 1 else "",
            modelo="remoto" if j.get("telecommuting") else None,
            publicada_em=j.get("published_on"),
            descricao=html_para_texto(j.get("description")),
            nivel_hint=j.get("experience"),
        ))
    return vagas
