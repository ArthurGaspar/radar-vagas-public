"""Chave canônica do link de uma vaga, para reconhecer a mesma vaga vinda de
fontes diferentes (ex: Remotar repostando uma vaga da Gupy ou do Ashby)."""

import base64
import json
import re
from urllib.parse import parse_qs, urlparse

_ULTIMO_TRECHO = re.compile(r"/(apply|application|applications)$")


def chave_url(url: str) -> str | None:
    if not url:
        return None
    u = urlparse(url if "://" in url else "https://" + url)
    host = (u.hostname or "").lower().removeprefix("www.")
    caminho = _ULTIMO_TRECHO.sub("", u.path.rstrip("/"))
    partes = [p for p in caminho.split("/") if p]
    if not host:
        return None

    # Gupy: /jobs/<id> ou /job/<base64 de {"jobId": id, ...}>
    if host.endswith(".gupy.io") and len(partes) >= 2:
        if partes[0] == "jobs" and partes[1].isdigit():
            return f"gupy:{partes[1]}"
        if partes[0] == "job":
            try:
                bruto = partes[1] + "=" * (-len(partes[1]) % 4)
                return f"gupy:{json.loads(base64.urlsafe_b64decode(bruto))['jobId']}"
            except Exception:
                pass
    gh = parse_qs(u.query).get("gh_jid")
    if gh:
        return f"greenhouse-job:{gh[0]}"
    if host.endswith("greenhouse.io"):
        m = re.search(r"/jobs/(\d+)", caminho)
        if m:
            return f"greenhouse-job:{m.group(1)}"
    if host in ("jobs.lever.co", "jobs.ashbyhq.com") and len(partes) >= 2:
        return f"{host.split('.')[1]}-job:{partes[1].lower()}"
    return f"url:{host}{caminho.lower()}"
