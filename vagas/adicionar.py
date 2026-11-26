"""`python -m vagas add <url>`: descobre ATS + slug a partir do link de uma vaga
(ou da página de vagas) e acrescenta a empresa em config/empresas.yaml."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import fontes, rede
from .config import CONFIG, carregar_empresas
from .modelos import Empresa

_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


def identificar(url: str, sondar: bool = True) -> tuple[str, str]:
    """Devolve (ats, slug) ou levanta ValueError explicando o que fazer.

    `sondar`: para domínios próprios (jobs.empresa.com), testa na rede se o
    site é um Recruitee ou Teamtailor por baixo."""
    if "://" not in url:
        url = "https://" + url
    u = urlparse(url)
    host = (u.hostname or "").lower()
    partes = [p for p in u.path.split("/") if p]

    def primeiro():
        if not partes:
            raise ValueError(f"não achei o identificador da empresa em {url}")
        return partes[0]

    if host.endswith("greenhouse.io"):
        alvo = parse_qs(u.query).get("for")
        return "greenhouse", alvo[0] if alvo else primeiro()
    if host == "jobs.lever.co":
        return "lever", primeiro()
    if host.endswith("lever.co"):
        raise ValueError("Lever EU (jobs.eu.lever.co) ainda não é suportado")
    if host == "jobs.ashbyhq.com":
        return "ashby", primeiro()
    if host.endswith(".myworkdaysite.com"):
        raise ValueError("Workday no formato myworkdaysite.com ainda não é suportado (só <empresa>.wdN.myworkdayjobs.com)")
    if host.endswith(".myworkdayjobs.com"):
        tenant_wd = host.split(".myworkday")[0]          # "nvidia.wd5"
        resto = [p for p in partes if not _LOCALE.match(p)]
        if not resto:
            raise ValueError("link do Workday sem o nome do site (ex: .../NVIDIAExternalCareerSite)")
        return "workday", f"{tenant_wd}/{resto[0]}"
    if host.endswith("smartrecruiters.com"):
        # Formatos: /ServiceNow/744000..., e o link de candidatura
        # /oneclick-ui/company/ServiceNow/publication/<uuid>?dcr_ci=ServiceNow
        if "company" in partes[:-1]:
            return "smartrecruiters", partes[partes.index("company") + 1]
        alvo = parse_qs(u.query).get("dcr_ci")
        if alvo:
            return "smartrecruiters", alvo[0]
        return "smartrecruiters", primeiro()
    if host == "apply.workable.com":
        if partes and partes[0] == "j":
            raise ValueError("link curto do Workable (/j/...) não tem o nome da empresa; abra a página de vagas da empresa e use esse link")
        return "workable", primeiro()
    if host.endswith(".teamtailor.com"):
        return "teamtailor", host.removesuffix(".teamtailor.com")
    if host.endswith(".recruitee.com"):
        return "recruitee", host.removesuffix(".recruitee.com")
    if host.endswith(".gupy.io") and host not in ("portal.gupy.io", "login.gupy.io"):
        return "gupy", host.removesuffix(".gupy.io")
    if host.endswith(".inhire.app") and not host.startswith("api."):
        return "inhire", host.removesuffix(".inhire.app")
    if "gh_jid" in u.query:
        raise ValueError("link de Greenhouse em domínio próprio; procure o link boards.greenhouse.io/<empresa> (ou o botão de candidatura) e use esse")
    if sondar and host:
        achado = _sondar_dominio(host)
        if achado:
            return achado
    raise ValueError(f"não reconheci o ATS de {host}. Suportados: {', '.join(fontes.ATS)}")


_EMAIL_RECRUITEE = re.compile(r"@([a-z0-9-]+)\.recruitee\.com")


def _sondar_dominio(host: str) -> tuple[str, str] | None:
    """Recruitee e Teamtailor permitem domínio próprio servindo a mesma API/feed."""
    try:
        dados = rede.get_json(f"https://{host}/api/offers/")
        if isinstance(dados, dict) and "offers" in dados:
            # O e-mail das vagas revela o subdomínio original (job.x@empresa.recruitee.com).
            m = _EMAIL_RECRUITEE.search(str(dados["offers"][:5]))
            return "recruitee", m.group(1) if m else host
    except Exception:
        pass
    try:
        rss = rede.get_texto(f"https://{host}/jobs.rss")
        if "teamtailor.com" in rss[:2000]:
            return "teamtailor", host
    except Exception:
        pass
    return None


def adicionar(url: str, nome: str | None, estagio: bool, validar: bool = True,
              caminho: Path = CONFIG / "empresas.yaml") -> str:
    ats, slug = identificar(url)
    for e in carregar_empresas(caminho):
        if e.ats == ats and e.slug.lower() == slug.lower():
            return f"já está na lista: {e.nome} ({ats}:{e.slug})"

    nome = nome or slug.split("/")[0].split(".")[0].replace("-", " ").title()
    empresa = Empresa(nome=nome, ats=ats, slug=slug, estagio=estagio)
    aviso = ""
    if validar:
        vagas = fontes.listar(empresa)  # levanta erro se o slug não existir
        aviso = f" · {len(vagas)} vagas abertas agora"
        if not vagas:
            # Alguns ATS (ex: SmartRecruiters) respondem "0 vagas" até para slug inexistente.
            aviso += f"\natenção: 0 vagas — confira se '{slug}' é mesmo o identificador da empresa no link"

    linha = f"  - {{nome: {_yaml(nome)}, ats: {ats}, slug: {_yaml(slug)}"
    linha += ", estagio: true}" if estagio else "}"
    texto = caminho.read_text(encoding="utf-8")
    if not texto.endswith("\n"):
        texto += "\n"
    caminho.write_text(texto + linha + "\n", encoding="utf-8")
    return f"adicionada: {nome} ({ats}:{slug}){aviso}"


def _yaml(valor: str) -> str:
    """Aspas só quando necessário, para manter o arquivo legível."""
    if re.fullmatch(r"[\w .&/-]+", valor) and not valor[0] in "-&" and valor.strip() == valor:
        return valor
    return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'
