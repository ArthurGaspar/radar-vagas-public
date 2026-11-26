"""Workday não tem API pública documentada; este é o endpoint que o próprio
site de vagas usa. Slug no formato "tenant.wdN/site", ex:
"nvidia.wd5/NVIDIAExternalCareerSite" para
https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
"""

import re
import threading
import time

import requests

from . import modelo, nova
from .. import rede
from ..texto import html_para_texto

POR_PAGINA = 20      # máximo aceito pelo Workday
MAX_PAGINAS = 50
PAUSA = 1.0          # segundos entre pedidos
ESPERAS_429 = (20, 60)  # esperas extras quando o Workday insiste em 429

# Todas as empresas Workday ficam em *.myworkdayjobs.com e o limite de pedidos
# parece valer por IP para o domínio inteiro. Por isso um pedido por vez, de
# todas as empresas Workday juntas, com pausa entre eles.
_fila = threading.Lock()


def _pedir(funcao, *args):
    for espera in (*ESPERAS_429, None):
        with _fila:
            try:
                return funcao(*args)
            except requests.exceptions.RetryError:
                if espera is None:
                    raise
            finally:
                time.sleep(PAUSA)
        time.sleep(espera)  # fora da fila: deixa outras empresas tentarem


def _recente(j) -> bool:
    """O Workday ordena da mais nova para a mais antiga ("Posted Today",
    "Posted Yesterday", "Posted 3 Days Ago"...). Rodando de hora em hora, só
    interessa o que é de hoje/ontem; sem a data, por segurança, conta como recente."""
    quando = (j.get("postedOn") or "").lower()
    return not quando or "today" in quando or "yesterday" in quando


def _partes(slug):
    host, site = slug.split("/", 1)
    tenant, wd = host.split(".", 1)
    return f"https://{tenant}.{wd}.myworkdayjobs.com", tenant, site


def _buscar(base, tenant, site, termo):
    url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    total, offset, itens = None, 0, []
    for _ in range(MAX_PAGINAS):
        dados = _pedir(rede.post_json, url, {"appliedFacets": {}, "limit": POR_PAGINA, "offset": offset, "searchText": termo})
        pagina = dados.get("jobPostings") or []
        if total is None:  # o Workday só informa o total na primeira página
            total = dados.get("total") or 0
        itens.extend(pagina)
        offset += POR_PAGINA
        # Página inteira com vagas antigas: o resto também é antigo.
        if not pagina or offset >= total or not any(_recente(j) for j in pagina):
            break
    return itens


def listar(empresa):
    base, tenant, site = _partes(empresa.slug)
    vistos, vagas = set(), []
    for termo in empresa.busca or [""]:
        for j in _buscar(base, tenant, site, termo):
            caminho = j.get("externalPath")
            if not caminho or caminho in vistos:
                continue
            vistos.add(caminho)
            id_vaga = (j.get("bulletFields") or [caminho])[0]
            local = j.get("locationsText", "")
            vagas.append(nova(
                empresa, id_vaga,
                titulo=j.get("title", ""),
                url=f"{base}/{site}{caminho}",
                # "3 Locations" não diz nada; o local real vem no detalhar
                local="" if re.match(r"\d+ locations?", local, re.I) else local,
                modelo=modelo(j.get("remoteType")),
                publicada_em=j.get("postedOn"),
                extra={"api": f"{base}/wday/cxs/{tenant}/{site}{caminho}"},
            ))
    return vagas


def detalhar(vaga):
    info = _pedir(rede.get_json, vaga.extra["api"]).get("jobPostingInfo", {})
    vaga.descricao = html_para_texto(info.get("jobDescription"))
    locais = [info.get("location", "")] + list(info.get("additionalLocations") or [])
    vaga.local = " / ".join(filter(None, locais)) or vaga.local
    vaga.modelo = modelo(info.get("remoteType")) or vaga.modelo
    vaga.url = info.get("externalUrl") or vaga.url
