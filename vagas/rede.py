"""Sessão HTTP compartilhada, com retry e uma sessão por thread."""

import json
import re
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 30
USER_AGENT = "radar-de-vagas/1.0 (monitor pessoal de vagas)"
_local = threading.local()


def sessao() -> requests.Session:
    s = getattr(_local, "sessao", None)
    if s is None:
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"})
        _local.sessao = s
    return s


def get_json(url: str, **kwargs):
    r = sessao().get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r.json()


def post_json(url: str, corpo: dict, **kwargs):
    r = sessao().post(url, json=corpo, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r.json()


def get_texto(url: str, **kwargs) -> str:
    r = sessao().get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text


def resumir_erro(exc: Exception) -> str:
    """Mensagem curta e legível para o log/Discord, sem URL nem traceback."""
    if isinstance(exc, requests.exceptions.RetryError) or "429" in str(exc)[:300]:
        return "429: o site limitou os pedidos (muitas requisições)"
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        codigo = exc.response.status_code
        dica = {403: "acesso bloqueado (anti-bot)", 404: "não encontrado (slug mudou?)"}.get(codigo, "")
        return f"HTTP {codigo}" + (f": {dica}" if dica else "")
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return "sem resposta (timeout/conexão)"
    return f"{type(exc).__name__}: {str(exc)[:120]}"


_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def next_data(url: str) -> dict:
    """pageProps embutido em páginas Next.js (usado pela Gupy)."""
    r = sessao().get(url, timeout=TIMEOUT)
    r.raise_for_status()
    m = _NEXT_DATA.search(r.content.decode("utf-8", errors="replace"))
    if not m:
        raise ValueError(f"página sem __NEXT_DATA__: {url}")
    return json.loads(m.group(1))["props"]["pageProps"]
