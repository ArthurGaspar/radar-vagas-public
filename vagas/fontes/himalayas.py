"""Himalayas (himalayas.app): vagas remotas do mundo todo, API pública.
Cada termo faz duas buscas, ambas da mais nova para a mais antiga:
  country=BR      vagas cuja lista de países permitidos inclui o Brasil
  worldwide=true  vagas sem restrição de país"""

from datetime import datetime, timezone
from urllib.parse import quote, urlparse

from .. import rede
from ..modelos import Vaga
from ..texto import html_para_texto, normalizar

API = "https://himalayas.app/jobs/api/search"
# Quando a vaga lista vários níveis, o mais júnior decide.
ORDEM_NIVEL = ["Entry-level", "Mid-level", "Senior", "Manager", "Director", "Executive"]


def buscar(termo: str, empresas_estagio: set[str], paginas: int = 1) -> list[Vaga]:
    itens = []
    for filtro in ("country=BR", "worldwide=true"):
        for pagina in range(1, paginas + 1):
            lote = rede.get_json(f"{API}?q={quote(termo)}&sort=recent&{filtro}&page={pagina}").get("jobs") or []
            itens += lote
            if len(lote) < 20:  # última página
                break
    vagas, vistos = [], set()
    for j in itens:
        guid = j.get("guid") or j.get("applicationLink")
        if not guid or guid in vistos:
            continue
        vistos.add(guid)
        paises = j.get("locationRestrictions") or []
        niveis = sorted(j.get("seniority") or [], key=lambda n: ORDEM_NIVEL.index(n) if n in ORDEM_NIVEL else 99)
        empresa = j.get("companyName", "")
        publicada = j.get("pubDate")
        vagas.append(Vaga(
            id=f"himalayas:{urlparse(guid).path.strip('/')}",
            fonte=f"himalayas-busca:{normalizar(termo)}",
            ats="himalayas",
            empresa=empresa or "(Himalayas)",
            titulo=j.get("title", ""),
            url=j.get("applicationLink") or guid,
            # Lista longa de países é comum ("Albania, Andorra, Argentina, Brazil...");
            # o filtro de local procura Brasil/LATAM dentro dela.
            local=", ".join(paises) if paises else "Worldwide",
            modelo="remoto",
            publicada_em=datetime.fromtimestamp(publicada, timezone.utc).isoformat() if publicada else None,
            descricao=html_para_texto(j.get("description")) or j.get("excerpt", ""),
            nivel_hint=niveis[0] if niveis else None,
            estagio_ok=normalizar(empresa) in empresas_estagio,
        ))
    return vagas
