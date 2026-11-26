"""Get on Board (getonbrd.com): portal de vagas de tecnologia com foco em LATAM.
API pública e documentada; a busca devolve da mais nova para a mais antiga."""

import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from . import modelo
from .. import rede
from ..modelos import Vaga
from ..texto import html_para_texto, normalizar

API = "https://www.getonbrd.com/api/v0/search/jobs"
MODELOS = {"fully_remote": "remoto", "remote_local": "remoto", "hybrid": "hibrido", "no_remote": "presencial"}


def _get(url: str):
    """O Cloudflare do Get on Board às vezes devolve 403 para IPs de datacenter
    (como os do GitHub Actions); costuma passar numa segunda tentativa."""
    try:
        return rede.get_json(url)
    except requests.exceptions.HTTPError as e:
        if e.response is None or e.response.status_code != 403:
            raise
        time.sleep(5)
        return rede.get_json(url)


def _nomes(rel) -> list[str]:
    dados = (rel or {}).get("data") or []
    if isinstance(dados, dict):
        dados = [dados]
    return [(d.get("attributes") or {}).get("name", "") for d in dados]


def buscar(termo: str, empresas_estagio: set[str], paginas: int = 1) -> list[Vaga]:
    expand = '["company","seniority","location_cities","location_tenants","location_regions"]'
    url = f"{API}?query={quote(termo)}&per_page=30&expand={expand}"
    itens = []
    for pagina in range(1, paginas + 1):
        dados = _get(f"{url}&page={pagina}")
        itens += dados.get("data") or []
        if pagina >= (dados.get("meta") or {}).get("total_pages", 1):
            break
    vagas = []
    for j in itens:
        a = j.get("attributes") or {}
        empresa = (_nomes(a.get("company")) or [""])[0]
        cidades = _nomes(a.get("location_cities"))
        # "countries" costuma vir só como ["Remote"]; os países realmente aceitos
        # (ex: remote_local só para o Chile) ficam em location_tenants/regions.
        permitidos = _nomes(a.get("location_tenants")) + _nomes(a.get("location_regions"))
        paises = permitidos or a.get("countries") or []
        # Os "headlines" viram cabeçalhos, o que permite pesar requisitos x diferenciais.
        partes = [
            a.get("description_headline", ""), html_para_texto(a.get("description")),
            a.get("functions_headline", ""), html_para_texto(a.get("functions")),
            a.get("desirable_headline") or "Nice to have", html_para_texto(a.get("desirable")),
        ]
        publicada = a.get("published_at")
        vagas.append(Vaga(
            id=f"getonbrd:{j['id']}",
            fonte=f"getonbrd-busca:{normalizar(termo)}",
            ats="getonbrd",
            empresa=empresa or "(Get on Board)",
            titulo=a.get("title", ""),
            url=(j.get("links") or {}).get("public_url", ""),
            local=" / ".join(filter(None, cidades + paises)),
            cidade=cidades[0] if len(cidades) == 1 else "",
            modelo=MODELOS.get(a.get("remote_modality")) or modelo(a.get("remote_modality")),
            publicada_em=datetime.fromtimestamp(publicada, timezone.utc).isoformat() if publicada else None,
            descricao="\n".join(p for p in partes if p),
            nivel_hint=(_nomes(a.get("seniority")) or [None])[0],
            estagio_ok=normalizar(empresa) in empresas_estagio,
        ))
    return vagas
