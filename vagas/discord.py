"""Envio para o Discord via webhook (não precisa de bot).

Variáveis de ambiente:
    DISCORD_WEBHOOK_ALTA          canal de alta compatibilidade
    DISCORD_WEBHOOK_PERSONALIZAR  canal das demais vagas
    DISCORD_WEBHOOK_LOGS          (opcional) erros de fontes, ex: slug que parou de funcionar
    DISCORD_WEBHOOK_URL           fallback único, se você preferir um canal só
"""

import json
import os
import time
from dataclasses import dataclass

import requests

from .match import Resultado
from .modelos import Vaga

VERDE, AMARELO, VERMELHO, CINZA = 0x2ECC71, 0xF1C40F, 0xE74C3C, 0x95A5A6
NIVEIS = {"junior": "🟢 Júnior", "pleno": "🟡 Pleno", "estagio": "🎓 Estágio", "sem_nivel": "⚪ Não informado", "senior": "🔴 Sênior"}
EMBEDS_POR_MENSAGEM = 10
CARACTERES_POR_MENSAGEM = 5500  # limite do Discord é 6000 somando todos os embeds


@dataclass
class Notificacao:
    vaga: Vaga
    nivel: str
    rotulo_local: str
    resultado: Resultado


def webhook(canal: str) -> str | None:
    return os.environ.get(f"DISCORD_WEBHOOK_{canal.upper()}") or os.environ.get("DISCORD_WEBHOOK_URL")


def canal(n: Notificacao, alta: int) -> str:
    s = n.resultado.score
    return "alta" if s is not None and s >= alta else "personalizar"


def _lista(itens: list[str], limite: int = 350) -> str:
    texto = ", ".join(itens) or "—"
    return texto if len(texto) <= limite else texto[: limite - 1].rsplit(",", 1)[0] + ", …"


def embed(n: Notificacao, alta: int, media: int) -> dict:
    v, r = n.vaga, n.resultado
    if r.score is None:
        cor, score = CINZA, "— (sem currículo)" if r.cv is None else "— (nenhum termo conhecido)"
    else:
        cor = VERDE if r.score >= alta else AMARELO if r.score >= media else VERMELHO
        score = f"**{r.score}%**" + (" ⚠️ poucos termos" if r.poucos_termos else "")
    idioma = {"pt": "PT", "en": "EN", "es": "ES"}.get(r.idioma, r.idioma)
    campos = [
        {"name": "Compatibilidade", "value": score, "inline": True},
        {"name": "Currículo", "value": f"CV {r.cv.upper()}" if r.cv else "—", "inline": True},
        {"name": "Nível", "value": NIVEIS.get(n.nivel, n.nivel), "inline": True},
        {"name": "Local", "value": n.rotulo_local[:1024] or "—", "inline": False},
    ]
    if r.batem:
        campos.append({"name": "✅ Tem no seu CV", "value": _lista(r.batem), "inline": False})
    if r.faltam:
        campos.append({"name": "❌ Pedido na vaga, não está no CV", "value": _lista(r.faltam), "inline": False})
    rodape = f"{v.ats} · vaga em {idioma}"
    if v.extra.get("banco_talentos"):
        rodape += " · banco de talentos"
    return {
        "title": v.titulo[:256] or "(sem título)",
        "url": v.url,
        "description": f"**{v.empresa}**",
        "color": cor,
        "fields": campos,
        "footer": {"text": rodape},
    }


def _lotes(embeds: list[tuple[Notificacao, dict]]):
    lote, tamanho = [], 0
    for n, e in embeds:
        t = len(json.dumps(e, ensure_ascii=False))
        if lote and (len(lote) == EMBEDS_POR_MENSAGEM or tamanho + t > CARACTERES_POR_MENSAGEM):
            yield lote
            lote, tamanho = [], 0
        lote.append((n, e))
        tamanho += t
    if lote:
        yield lote


def _postar(url: str, corpo: dict) -> None:
    for _ in range(5):
        r = requests.post(url, json=corpo, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        r.raise_for_status()
        time.sleep(1)  # webhooks aceitam ~5 mensagens a cada 2s
        return
    raise RuntimeError("Discord continuou devolvendo 429")


def enviar(notificacoes: list[Notificacao], alta: int, media: int) -> list[Notificacao]:
    """Envia em lotes; devolve as notificações entregues com sucesso."""
    entregues = []
    por_canal: dict[str, list[Notificacao]] = {}
    for n in notificacoes:
        por_canal.setdefault(canal(n, alta), []).append(n)
    for nome, lista in por_canal.items():
        url = webhook(nome)
        if not url:
            print(f"[discord] sem webhook para o canal '{nome}'; {len(lista)} vaga(s) não enviadas")
            continue
        for lote in _lotes([(n, embed(n, alta, media)) for n in lista]):
            try:
                _postar(url, {"username": "Radar de Vagas", "embeds": [e for _, e in lote]})
                entregues.extend(n for n, _ in lote)
            except Exception as e:  # o lote volta na próxima execução
                print(f"[discord] falha ao enviar lote para '{nome}': {e}")
    return entregues


def enviar_log(titulo: str, linhas: list[str] | None = None) -> None:
    """Manda para o canal de logs, quebrando em várias mensagens se passar do
    limite de 2000 caracteres do Discord (sem cortar linha no meio)."""
    url = os.environ.get("DISCORD_WEBHOOK_LOGS")
    if not url:
        return
    for m in dividir_mensagens(titulo, linhas or []):
        try:
            _postar(url, {"username": "Radar de Vagas", "content": m})
        except Exception as e:
            print(f"[discord] falha ao enviar log: {e}")


def dividir_mensagens(titulo: str, linhas: list[str], limite: int = 1900) -> list[str]:
    mensagens, atual = [], titulo
    for linha in linhas:
        linha = linha[:limite]
        if len(atual) + 1 + len(linha) > limite:
            mensagens.append(atual)
            atual = linha
        else:
            atual += "\n" + linha
    mensagens.append(atual)
    return mensagens
