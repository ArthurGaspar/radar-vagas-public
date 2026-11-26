from . import modelo, nova
from .. import rede
from ..texto import html_para_texto


def listar(empresa):
    dados = rede.get_json(f"https://api.lever.co/v0/postings/{empresa.slug}?mode=json")
    vagas = []
    for j in dados:
        cat = j.get("categories") or {}
        locais = cat.get("allLocations") or [cat.get("location", "")]
        partes = [j.get("descriptionPlain", "")]
        for bloco in j.get("lists") or []:
            partes.append(bloco.get("text", ""))
            partes.append(html_para_texto(bloco.get("content")))
        partes.append(j.get("additionalPlain", ""))
        vagas.append(nova(
            empresa, j["id"],
            titulo=j.get("text", ""),
            url=j.get("hostedUrl", ""),
            local=" / ".join(filter(None, locais + [j.get("country") or ""])),
            modelo=modelo(j.get("workplaceType")),
            publicada_em=str(j.get("createdAt", "")),
            descricao="\n".join(p for p in partes if p),
            nivel_hint=cat.get("commitment"),
        ))
    return vagas
