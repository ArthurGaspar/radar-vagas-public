"""Uma execução do radar: coleta → novas → filtros → score → Discord."""

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import discord, fontes, rede
from .config import Config
from .dedup import chave_url
from .discord import Notificacao
from .estado import Estado
from .filtros import Filtros
from .fontes import getonbrd, gupy, himalayas, remotar
from .match import Matcher
from .modelos import Vaga
from .texto import normalizar

TRABALHADORES = 8

# Portais com busca por palavra-chave: chave em filtros.yaml -> função de busca.
# A ordem importa: na mesma execução, a primeira fonte que trouxer uma vaga é a
# que notifica; ATS das empresas vêm antes de tudo, agregadores por último.
BUSCAS = {
    "buscas_gupy": gupy.buscar,
    "buscas_getonbrd": getonbrd.buscar,
    "buscas_remotar": remotar.buscar,
    "buscas_himalayas": himalayas.buscar,
}


def coletar(cfg: Config, paginas: int = 1) -> tuple[dict[str, list[Vaga]], dict[str, str]]:
    """Lista as vagas de todas as fontes. Devolve (vagas por fonte, erros por fonte).

    `paginas`: quantas páginas cada portal de busca lê por termo. Os portais só
    devolvem as N vagas mais recentes; depois de uma pausa longa (madrugada)
    pode ter surgido mais que N, então vale ler mais fundo."""
    por_fonte: dict[str, list[Vaga]] = {}
    erros: dict[str, str] = {}

    with ThreadPoolExecutor(TRABALHADORES) as pool:
        futuros = {pool.submit(fontes.listar, e): e for e in cfg.empresas}
        for f in as_completed(futuros):
            e = futuros[f]
            try:
                por_fonte[e.chave] = f.result()
            except Exception as exc:
                erros[f"{e.nome} ({e.chave})"] = rede.resumir_erro(exc)

    # Buscas por termo: dentro de cada portal em sequência e com pausa (poucos
    # pedidos por hora, sem martelar ninguém); os portais rodam em paralelo.
    estagio = {normalizar(e.nome) for e in cfg.empresas if e.estagio}
    estagio |= {e.slug for e in cfg.empresas if e.estagio and e.ats == "gupy"}

    def rodar_buscas(chave):
        nome = chave.removeprefix("buscas_")
        resultado, falhas = {}, {}
        for termo in cfg.filtros.get(chave) or []:
            fonte = f"{nome}-busca:{normalizar(termo)}"
            try:
                resultado[fonte] = BUSCAS[chave](termo, estagio, paginas)
            except Exception as exc:
                falhas[fonte] = rede.resumir_erro(exc)
            time.sleep(1)
        return resultado, falhas

    with ThreadPoolExecutor(len(BUSCAS)) as pool:
        for resultado, falhas in pool.map(rodar_buscas, BUSCAS):  # map preserva a ordem
            por_fonte.update(resultado)
            erros.update(falhas)
    return por_fonte, erros


def calcular_chaves(vagas: list[Vaga]) -> None:
    """Id da vaga + chave do link (em v.extra["chaves"]), para reconhecer a mesma
    vaga vinda de outra fonte. Link repetido dentro da mesma fonte (ex: página
    genérica de carreiras usada em várias vagas) não serve como chave."""
    links = [chave_url(v.url) for v in vagas]
    contagem = Counter(links)
    for v, k in zip(vagas, links):
        v.extra["chaves"] = [v.id, k] if k and k != v.id and contagem[k] == 1 else [v.id]


def chaves(v: Vaga) -> list[str]:
    return v.extra.get("chaves") or [v.id]


def avaliar(vagas: list[Vaga], cfg: Config) -> tuple[list[Notificacao], dict[str, int]]:
    """Aplica filtros e score às vagas novas. Devolve notificações e contagem de descartes."""
    filtros = Filtros(cfg.filtros)
    matcher = Matcher(cfg.skills, cfg.cv)
    descartes = {"titulo": 0, "nivel": 0, "local": 0, "erro_detalhe": 0}

    candidatas = []
    for v in vagas:
        if not filtros.titulo_ok(v.titulo):
            descartes["titulo"] += 1
            continue
        nivel = filtros.nivel(v.titulo, v.nivel_hint)
        if not filtros.nivel_ok(nivel, v.estagio_ok):
            descartes["nivel"] += 1
            continue
        candidatas.append((v, nivel))

    # Detalhe (descrição) só para quem passou nos filtros baratos.
    def detalhar(item):
        v, _ = item
        fontes.detalhar(v)
        return item

    prontas = []
    with ThreadPoolExecutor(TRABALHADORES) as pool:
        futuros = [pool.submit(detalhar, c) for c in candidatas]
        for f, (v, nivel) in zip(futuros, candidatas):
            try:
                f.result()
            except Exception as exc:
                # Sem descrição ainda dá para notificar; o score fica pelo título.
                descartes["erro_detalhe"] += 1
                print(f"[detalhe] {v.empresa} · {v.titulo}: {exc}")
            prontas.append((v, nivel))

    notificacoes = []
    for v, nivel in prontas:
        ok, rotulo = filtros.local(v)
        if not ok:
            descartes["local"] += 1
            continue
        notificacoes.append(Notificacao(v, nivel, rotulo, matcher.avaliar(v.titulo, v.descricao)))

    # Júnior primeiro, depois maior score.
    prioridade = {"junior": 0, "estagio": 1, "sem_nivel": 2, "pleno": 3}
    notificacoes.sort(key=lambda n: (prioridade.get(n.nivel, 9), -(n.resultado.score or 0)))
    return notificacoes, descartes


def classificar_pausa(ultima: datetime | None, agora: datetime, exec_cfg: dict) -> str:
    """normal | madrugada | inesperada.

    madrugada: primeira execução do dia, dentro da janela da manhã, vindo da
    pausa noturna planejada (23h17 → 6h17). O acumulado é notificado.
    inesperada: qualquer outra pausa longa (PC desligado, mudança...). O
    acumulado é registrado sem notificar.
    """
    if ultima is None:
        return "normal"
    horas = (agora - ultima).total_seconds() / 3600
    if horas <= float(exec_cfg.get("pausa_longa_horas", 2)):
        return "normal"
    fuso = timezone(timedelta(hours=float(exec_cfg.get("fuso_utc", -3))))
    agora_l, ultima_l = agora.astimezone(fuso), ultima.astimezone(fuso)
    inicio_hoje = agora_l.replace(hour=int(exec_cfg.get("inicio_dia", 6)), minute=0, second=0, microsecond=0)
    na_janela_da_manha = inicio_hoje <= agora_l <= inicio_hoje + timedelta(hours=float(exec_cfg.get("janela_manha_horas", 2)))
    so_a_noite = horas <= float(exec_cfg.get("max_pausa_noturna_horas", 9))
    if na_janela_da_manha and ultima_l < inicio_hoje and so_a_noite:
        return "madrugada"
    return "inesperada"


def executar(cfg: Config, caminho_estado: Path, enviar: bool = True, silencioso: bool = False) -> None:
    """`silencioso`: registra todas as vagas novas sem notificar (descarta o acumulado)."""
    inicio = time.time()
    estado = Estado(caminho_estado)
    exec_cfg = cfg.filtros.get("execucao") or {}
    agora = datetime.now(timezone.utc)
    pausa = (agora - estado.ultima_execucao).total_seconds() / 3600 if estado.ultima_execucao else None
    tipo = "inesperada" if silencioso else classificar_pausa(estado.ultima_execucao, agora, exec_cfg)
    # Depois de qualquer pausa, lê mais fundo: na madrugada para notificar tudo,
    # na inesperada para registrar todo o acumulado (senão ele vaza depois).
    paginas = int(exec_cfg.get("paginas_apos_pausa", 3)) if tipo != "normal" else 1
    if tipo == "madrugada":
        print(f"primeira execução do dia (última há {pausa:.1f}h): lendo {paginas} páginas por termo nos portais")
    elif tipo == "inesperada":
        print("pausa inesperada" + (f" (última há {pausa:.1f}h)" if pausa else "")
              + ": as vagas novas serão registradas sem notificar")
    por_fonte, erros = coletar(cfg, paginas)

    def marcar(v: Vaga):
        for k in chaves(v):
            estado.marcar(k)

    novas: dict[str, Vaga] = {}
    da_rodada: set[str] = set()
    silenciosas = duplicadas = 0
    for fonte, vagas in por_fonte.items():
        primeira_vez = estado.fonte_nova(fonte)
        calcular_chaves(vagas)
        for v in vagas:
            ks = chaves(v)
            if any(k in da_rodada for k in ks):
                duplicadas += 1  # outra fonte já trouxe esta vaga nesta execução
                continue
            da_rodada.update(ks)
            if any(estado.ja_vista(k) for k in ks):
                marcar(v)  # renova a data: a vaga continua aberta
            elif primeira_vez:
                marcar(v)
                silenciosas += 1
            else:
                novas[v.id] = v
        estado.registrar_fonte(fonte)

    if tipo == "inesperada":
        # Vaga que surgiu com o radar parado já perdeu a vantagem de chegar
        # cedo; despejar o acumulado só polui o Discord.
        for v in novas.values():
            marcar(v)
        notificacoes, descartes = [], {"titulo": 0, "nivel": 0, "local": 0}
    else:
        # Tudo que é novo entra como visto, menos o que for notificado: essas só
        # são marcadas depois que o Discord confirmar (se falhar, tentam de novo).
        notificacoes, descartes = avaliar(list(novas.values()), cfg)
        a_notificar = {n.vaga.id for n in notificacoes}
        for v in novas.values():
            if v.id not in a_notificar:
                marcar(v)

    notif_cfg = cfg.filtros.get("notificacao") or {}
    limite = int(notif_cfg.get("max_por_execucao_manha" if tipo == "madrugada" else "max_por_execucao",
                               100 if tipo == "madrugada" else 40))
    # Falha isolada (um 429, um timeout) é normal e se resolve na hora seguinte;
    # o Discord só é avisado quando a mesma fonte falha várias vezes seguidas.
    alertas = estado.registrar_falhas(erros, int(notif_cfg.get("alertar_apos_falhas", 3)))
    match_cfg = cfg.filtros.get("match") or {}
    alta, media = int(match_cfg.get("alta", 75)), int(match_cfg.get("media", 50))
    lote, adiadas = notificacoes[:limite], notificacoes[limite:]

    if enviar:
        entregues = discord.enviar(lote, alta, media)
        for n in entregues:
            marcar(n.vaga)
        estado.salvar()
    else:
        entregues = []
        for n in lote:
            imprimir(n, alta)

    total = sum(len(v) for v in por_fonte.values())
    print(
        f"\n{len(por_fonte)} fontes ok, {len(erros)} com erro · {total} vagas abertas · "
        f"{silenciosas} registradas sem notificar (fonte nova) · {duplicadas} repetidas entre fontes · "
        f"{len(novas)} novas\n"
        f"descartadas: título {descartes['titulo']}, nível {descartes['nivel']}, local {descartes['local']} · "
        f"notificar: {len(notificacoes)} (enviadas {len(entregues)}, adiadas {len(adiadas)}) · "
        f"{time.time() - inicio:.0f}s"
    )
    if not cfg.cv:
        print("aviso: nenhum currículo em curriculo/ — o score fica vazio")
    if erros:
        linhas = "\n".join(f"- {k}: {v}" for k, v in sorted(erros.items()))
        print(f"\nfontes com erro:\n{linhas}")
    if tipo == "inesperada" and enviar and novas:
        motivo = "Acumulado descartado manualmente" if silencioso or not pausa else f"O radar ficou {pausa:.1f}h sem rodar"
        discord.enviar_log(f"⏸️ {motivo}: {len(novas)} vaga(s) acumulada(s) registradas sem notificar. "
                           "Daqui pra frente, só as novas.")
    if alertas and enviar:
        linhas = [f"- **{k}** ({n} execuções seguidas): {erros[k]}" for k, n in sorted(alertas.items())]
        discord.enviar_log("⚠️ Fonte(s) falhando repetidamente:", linhas)


def imprimir(n: Notificacao, alta: int) -> None:
    r = n.resultado
    score = "—" if r.score is None else f"{r.score}%"
    marca = "★" if r.score is not None and r.score >= alta else " "
    print(f"{marca} [{score:>4}] {n.vaga.empresa} · {n.vaga.titulo}")
    print(f"         {discord.NIVEIS.get(n.nivel, n.nivel)} · {n.rotulo_local} · CV {(r.cv or '-').upper()}")
    if r.faltam:
        print(f"         faltam: {', '.join(r.faltam[:10])}")
    print(f"         {n.vaga.url}")
