"""Gupy não tem API pública para candidatos, mas as páginas são Next.js e trazem
os dados em JSON embutido (__NEXT_DATA__):

- empresa.gupy.io            → todas as vagas abertas da empresa
- empresa.gupy.io/jobs/<id>  → descrição completa de uma vaga
- portal.gupy.io/job-search  → busca por termo em TODAS as empresas da Gupy,
                               ordenada da mais recente para a mais antiga

O id da vaga na Gupy é global, então a mesma vaga vinda da empresa ou da busca
recebe o mesmo id (gupy:<id>) e não é notificada duas vezes.
"""

import re
from urllib.parse import quote, urlparse

from . import modelo
from .. import rede
from ..modelos import Vaga
from ..texto import html_para_texto, normalizar

NIVEL_POR_TIPO = {
    "vacancy_type_internship": "internship",
    "vacancy_type_apprentice": "internship",
    "vacancy_type_trainee": "trainee",
}


def _local(cidade, estado):
    return ", ".join(filter(None, [cidade, estado, "Brasil"]))


def listar(empresa):
    pp = rede.next_data(f"https://{empresa.slug}.gupy.io/")
    vagas = []
    for j in pp.get("jobs") or []:
        trabalho = j.get("workplace") or {}
        end = trabalho.get("address") or {}
        vagas.append(Vaga(
            id=f"gupy:{j['id']}",
            fonte=empresa.chave,
            ats="gupy",
            empresa=empresa.nome,
            titulo=(j.get("title") or "").strip(),
            url=f"https://{empresa.slug}.gupy.io/jobs/{j['id']}",
            local=_local(end.get("city"), end.get("stateShortName") or end.get("state")),
            cidade=end.get("city") or "",
            modelo=modelo(trabalho.get("workplaceType")),
            nivel_hint=NIVEL_POR_TIPO.get(j.get("type")),
            estagio_ok=empresa.estagio,
            extra={"pagina": f"https://{empresa.slug}.gupy.io/jobs/{j['id']}",
                   "banco_talentos": j.get("type") == "vacancy_type_talent_pool"},
        ))
    return vagas


def detalhar(vaga):
    job = rede.next_data(vaga.extra["pagina"]).get("job") or {}
    partes = [
        html_para_texto(job.get("description")),
        "Responsabilidades e atribuições", html_para_texto(job.get("responsibilities")),
        "Requisitos e qualificações", html_para_texto(job.get("prerequisites")),
        "Diferenciais", html_para_texto(job.get("relevantExperiences")),
    ]
    vaga.descricao = "\n".join(p for p in partes if p)
    vaga.publicada_em = job.get("publishedAt") or vaga.publicada_em


def buscar(termo: str, empresas_estagio: set[str], paginas: int = 1) -> list[Vaga]:
    """Busca no portal. `empresas_estagio`: nomes/slugs normalizados com estágio liberado."""
    itens = []
    for pagina in range(1, paginas + 1):
        pp = rede.next_data(f"https://portal.gupy.io/job-search/term={quote(termo)}&page={pagina}")
        lote = (pp.get("initialJobList") or {}).get("data") or []
        itens += lote
        if len(lote) < 12:  # última página
            break
    vagas = []
    for j in itens:
        subdominio = urlparse(j.get("jobUrl", "")).hostname or ""
        subdominio = subdominio.removesuffix(".gupy.io")
        nome = j.get("careerPageName") or subdominio
        vagas.append(Vaga(
            id=f"gupy:{j['id']}",
            fonte=f"gupy-busca:{normalizar(termo)}",
            ats="gupy",
            empresa=nome,
            titulo=(j.get("name") or "").strip(),
            # Páginas desativadas vêm com subdomínio tipo "empresa&123&inactive".
            url=(f"https://{subdominio}.gupy.io/jobs/{j['id']}" if re.fullmatch(r"[a-z0-9-]+", subdominio)
                 else j.get("jobUrl", "")),
            local=_local(j.get("city"), j.get("state")),
            cidade=j.get("city") or "",
            modelo=modelo(j.get("workplaceType")),
            publicada_em=j.get("publishedDate"),
            descricao=(j.get("description") or "").strip(),
            nivel_hint=NIVEL_POR_TIPO.get(j.get("type")),
            estagio_ok=normalizar(nome) in empresas_estagio or subdominio in empresas_estagio,
            extra={"banco_talentos": j.get("type") == "vacancy_type_talent_pool"},
        ))
    return vagas
