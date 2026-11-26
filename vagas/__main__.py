"""
Uso:
  python -m vagas run [--dry-run] [--silencioso] [--estado CAMINHO]
      Execução normal: busca vagas novas, notifica no Discord e salva o estado.
      --dry-run imprime no terminal em vez de notificar e não salva nada.
      --silencioso registra as vagas novas sem notificar (descarta o acumulado,
      ex: depois de o PC ficar desligado ou de uma mudança grande nos filtros).

  python -m vagas add URL [--nome NOME] [--estagio] [--sem-validar]
      Adiciona a empresa de um link de vaga em config/empresas.yaml.

  python -m vagas testar EMPRESA [--todas]
      Aplica filtros e score a TODAS as vagas abertas de uma empresa (ignora o
      estado). Bom para calibrar filtros.yaml e skills.yaml. EMPRESA pode ser o
      nome, o slug ou "ats:slug" (não precisa estar no YAML). --todas mostra
      também por que cada vaga foi descartada.

  python -m vagas demo
      Roda filtros e score sobre vagas fictícias (exemplos/vagas_exemplo.json),
      offline, sem Discord. Mostra o que seria notificado e por que o resto caiu.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from . import fontes
from .config import RAIZ, carregar
from .modelos import Empresa, Vaga


def _carregar_env():
    """Lê um .env simples (CHAVE=valor) para rodar localmente."""
    caminho = RAIZ / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def _achar_empresa(cfg, alvo: str) -> Empresa:
    for e in cfg.empresas:
        if alvo.lower() in (e.nome.lower(), e.slug.lower(), e.chave.lower()):
            return e
    if ":" in alvo:
        ats, slug = alvo.split(":", 1)
        return Empresa(nome=slug, ats=ats, slug=slug)
    sys.exit(f"empresa '{alvo}' não está em empresas.yaml; use ats:slug (ex: greenhouse:stripe)")


def _motivo(f, v) -> str:
    """Por que a vaga cai nos filtros baratos (ou "passa")."""
    nivel = f.nivel(v.titulo, v.nivel_hint)
    if not f.titulo_ok(v.titulo):
        return "título"
    if not f.nivel_ok(nivel, v.estagio_ok):
        return f"nível ({nivel})"
    ok, rotulo = f.local(v)
    return "passa" if ok else f"local ({rotulo})"


def demo(cfg):
    from .filtros import Filtros
    from .radar import avaliar, imprimir

    caminho = RAIZ / "exemplos" / "vagas_exemplo.json"
    vagas = [
        Vaga(id=f"demo:{i}", fonte="demo", ats="demo", url=f"https://exemplo.com/vagas/{i}", **dados)
        for i, dados in enumerate(json.loads(caminho.read_text(encoding="utf-8")), 1)
    ]
    f = Filtros(cfg.filtros)
    print(f"{len(vagas)} vagas de exemplo · currículo: {', '.join(cfg.cv) or 'nenhum'}\n")
    print("Filtros:")
    for v in vagas:
        print(f"  {_motivo(f, v):<45.45} {v.empresa} · {v.titulo}")
    notificacoes, _ = avaliar(vagas, cfg)
    alta = int((cfg.filtros.get("match") or {}).get("alta", 75))
    print(f"\nSeriam notificadas ({len(notificacoes)}), com o score de compatibilidade:\n")
    for n in notificacoes:
        imprimir(n, alta)
    print(f"\n★ = score >= {alta}%: canal de alta compatibilidade (mandar o CV como está)")


def testar(cfg, alvo: str, todas: bool):
    from .filtros import Filtros
    from .radar import avaliar, imprimir

    empresa = _achar_empresa(cfg, alvo)
    vagas = fontes.listar(empresa)
    print(f"{empresa.nome}: {len(vagas)} vagas abertas\n")
    if todas:
        f = Filtros(cfg.filtros)
        for v in vagas:
            motivo = _motivo(f, v)
            print(f"  {motivo + ('*' if motivo == 'passa' else ''):<40.40} {v.titulo}  [{v.local}]")
        print("\n* antes de buscar a descrição; o local pode mudar no detalhe (Workday)\n")
    notificacoes, descartes = avaliar(vagas, cfg)
    match = cfg.filtros.get("match") or {}
    for n in notificacoes:
        imprimir(n, int(match.get("alta", 75)))
    print(f"\n{len(notificacoes)} passariam · descartadas: {descartes}")


def main():
    _carregar_env()
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8")  # emojis no terminal do Windows

    p = argparse.ArgumentParser(prog="python -m vagas", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="busca vagas novas e notifica")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--silencioso", action="store_true", help="registra as novas sem notificar")
    r.add_argument("--estado", type=Path, default=RAIZ / "estado" / "vistos.json")

    a = sub.add_parser("add", help="adiciona empresa a partir de um link")
    a.add_argument("url")
    a.add_argument("--nome")
    a.add_argument("--estagio", action="store_true", help="mostrar estágios desta empresa")
    a.add_argument("--sem-validar", action="store_true", help="não consulta o ATS antes de salvar")

    sub.add_parser("demo", help="filtros e score sobre vagas fictícias, offline")

    t = sub.add_parser("testar", help="aplica filtros e score às vagas atuais de uma empresa")
    t.add_argument("empresa")
    t.add_argument("--todas", action="store_true")

    args = p.parse_args()
    if args.cmd == "add":
        from .adicionar import adicionar
        try:
            print(adicionar(args.url, args.nome, args.estagio, validar=not args.sem_validar))
        except Exception as e:
            sys.exit(f"erro: {e}")
    elif args.cmd == "demo":
        demo(carregar())
    elif args.cmd == "testar":
        testar(carregar(), args.empresa, args.todas)
    elif args.cmd == "run" or args.cmd is None:
        from .radar import executar
        dry = getattr(args, "dry_run", False)
        estado = getattr(args, "estado", RAIZ / "estado" / "vistos.json")
        executar(carregar(), estado, enviar=not dry, silencioso=getattr(args, "silencioso", False))


if __name__ == "__main__":
    main()
