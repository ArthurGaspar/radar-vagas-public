from . import nova
from .. import rede
from ..texto import html_para_texto

API = "https://api.smartrecruiters.com/v1/companies"
POR_PAGINA = 100
MAX_PAGINAS = 60


def listar(empresa):
    vagas, offset = [], 0
    for _ in range(MAX_PAGINAS):
        dados = rede.get_json(f"{API}/{empresa.slug}/postings?limit={POR_PAGINA}&offset={offset}")
        for j in dados.get("content", []):
            loc = j.get("location") or {}
            if loc.get("remote"):
                modelo_trab = "remoto"
            elif loc.get("hybrid"):
                modelo_trab = "hibrido"
            else:
                modelo_trab = None
            vagas.append(nova(
                empresa, j["id"],
                titulo=j.get("name", ""),
                url=f"https://jobs.smartrecruiters.com/{empresa.slug}/{j['id']}",
                local=loc.get("fullLocation", ""),
                cidade=loc.get("city", ""),
                modelo=modelo_trab,
                publicada_em=j.get("releasedDate"),
                nivel_hint=(j.get("experienceLevel") or {}).get("id"),
                extra={"ref": j.get("ref")},
            ))
        offset += POR_PAGINA
        if offset >= dados.get("totalFound", 0):
            break
    return vagas


def detalhar(vaga):
    j = rede.get_json(vaga.extra["ref"])
    secoes = (j.get("jobAd") or {}).get("sections") or {}
    partes = []
    for chave in ("jobDescription", "qualifications", "additionalInformation"):
        s = secoes.get(chave) or {}
        partes += [s.get("title", ""), html_para_texto(s.get("text"))]
    vaga.descricao = "\n".join(p for p in partes if p)
    vaga.url = j.get("postingUrl") or vaga.url
