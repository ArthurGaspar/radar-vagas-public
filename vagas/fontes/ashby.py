from . import modelo, nova
from .. import rede


def listar(empresa):
    dados = rede.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{empresa.slug}")
    vagas = []
    for j in dados.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locais = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        pais = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "")
        modelo_trab = modelo(j.get("workplaceType")) or ("remoto" if j.get("isRemote") else None)
        vagas.append(nova(
            empresa, j["id"],
            titulo=j.get("title", ""),
            url=j.get("jobUrl", ""),
            local=" / ".join(dict.fromkeys(filter(None, locais + [pais]))),
            modelo=modelo_trab,
            publicada_em=j.get("publishedAt"),
            descricao=j.get("descriptionPlain", ""),
        ))
    return vagas
