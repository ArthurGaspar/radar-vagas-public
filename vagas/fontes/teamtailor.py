"""Teamtailor só tem API com chave; o feed RSS público já traz tudo.
Slug = subdomínio (empresa.teamtailor.com) ou domínio próprio (careers.empresa.com).
"""

import xml.etree.ElementTree as ET

from . import modelo, nova
from .. import rede
from ..texto import html_para_texto

TT = "{https://teamtailor.com/locations}"
REMOTO = {"fully": "remoto", "hybrid": "hibrido", "onsite": "presencial", "none": "presencial"}


def _url(slug):
    return f"https://{slug}/jobs.rss" if "." in slug else f"https://{slug}.teamtailor.com/jobs.rss"


def listar(empresa):
    raiz = ET.fromstring(rede.get_texto(_url(empresa.slug)).encode("utf-8"))
    vagas = []
    for item in raiz.iter("item"):
        locais = [loc.findtext(f"{TT}name") or "" for loc in item.iter(f"{TT}location")]
        cidades = [loc.findtext(f"{TT}city") or "" for loc in item.iter(f"{TT}location")]
        status = (item.findtext("remoteStatus") or "").lower()
        vagas.append(nova(
            empresa, item.findtext("guid") or item.findtext("link"),
            titulo=item.findtext("title") or "",
            url=item.findtext("link") or "",
            local=" / ".join(filter(None, locais)),
            cidade=cidades[0] if len(cidades) == 1 else "",
            modelo=REMOTO.get(status) or modelo(status),
            publicada_em=item.findtext("pubDate"),
            descricao=html_para_texto(item.findtext("description")),
        ))
    return vagas
