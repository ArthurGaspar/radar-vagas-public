"""Remotar (remotar.com.br): vagas remotas abertas a quem está no Brasil.
Usa a API que o próprio site consome; a busca vem da mais nova para a mais antiga.
Muitas vagas são repostagens (Gupy, Ashby, Greenhouse...); o link de
candidatura (`externalLink`) é usado como URL para a deduplicação pegar."""

from urllib.parse import quote

from .. import rede
from ..modelos import Vaga
from ..texto import html_para_texto, normalizar

API = "https://api.remotar.com.br/jobs"


def buscar(termo: str, empresas_estagio: set[str], paginas: int = 1) -> list[Vaga]:
    itens = []
    for pagina in range(1, paginas + 1):
        dados = rede.get_json(f"{API}?search={quote(termo)}&page={pagina}")
        itens += dados.get("data") or []
        if pagina >= (dados.get("meta") or {}).get("last_page", 1):
            break
    vagas = []
    for j in itens:
        if j.get("active") is False or j.get("expired"):
            continue
        empresa = j.get("companyDisplayName") or (j.get("company") or {}).get("name", "")
        requisitos = j.get("jobRequirements") or []
        obrigatorios = [r.get("description", "") for r in requisitos if r.get("mandatory")]
        desejaveis = [r.get("description", "") for r in requisitos if not r.get("mandatory")]
        partes = [j.get("subtitle", ""), html_para_texto(j.get("description"))]
        if obrigatorios:
            partes += ["Requisitos"] + [f"- {r}" for r in obrigatorios]
        if desejaveis:
            partes += ["Diferenciais"] + [f"- {r}" for r in desejaveis]
        pais = j.get("country")
        pais = pais.get("name", "") if isinstance(pais, dict) else (pais or "")
        local = ", ".join(filter(None, [j.get("city"), j.get("state"), pais])) or "Brasil"
        tipo = (j.get("type") or "").lower()
        vagas.append(Vaga(
            id=f"remotar:{j['id']}",
            fonte=f"remotar-busca:{normalizar(termo)}",
            ats="remotar",
            empresa=empresa or "(Remotar)",
            titulo=j.get("title", ""),
            url=j.get("externalLink") or f"https://remotar.com.br/job/{j['id']}",
            local=local,
            cidade=j.get("city") or "",
            modelo="remoto" if tipo == "remote" else "hibrido" if tipo == "hybrid" else None,
            publicada_em=j.get("createdAt"),
            descricao="\n".join(p for p in partes if p),
            estagio_ok=normalizar(empresa) in empresas_estagio,
        ))
    return vagas
