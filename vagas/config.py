from dataclasses import dataclass
from pathlib import Path

import yaml

from .fontes import ATS
from .modelos import Empresa

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config"
CURRICULO = RAIZ / "curriculo"


@dataclass
class Config:
    empresas: list[Empresa]
    filtros: dict
    skills: dict[str, list[str]]   # nome exibido -> sinônimos procurados no texto
    cv: dict[str, str]             # "pt"/"en" -> texto do currículo (pode faltar)


def _ler(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def carregar_empresas(caminho: Path = CONFIG / "empresas.yaml") -> list[Empresa]:
    empresas = []
    for i, e in enumerate(_ler(caminho).get("empresas") or [], 1):
        faltando = [k for k in ("nome", "ats", "slug") if not e.get(k)]
        if faltando:
            raise ValueError(f"empresas.yaml, item {i}: faltam os campos {faltando}")
        if e["ats"] not in ATS:
            raise ValueError(f"empresas.yaml, {e['nome']}: ats {e['ats']!r} inválido (opções: {', '.join(ATS)})")
        busca = e.get("busca") or []
        empresas.append(Empresa(
            nome=str(e["nome"]), ats=e["ats"], slug=str(e["slug"]).strip(),
            estagio=bool(e.get("estagio", False)),
            busca=[busca] if isinstance(busca, str) else list(busca),
        ))
    return empresas


def carregar_skills(caminho: Path = CONFIG / "skills.yaml") -> dict[str, list[str]]:
    skills = {}
    for grupo in _ler(caminho).values():
        for nome, sinonimos in (grupo or {}).items():
            # O nome não entra como sinônimo: "Go", "R" e "C" casariam com qualquer texto.
            skills[str(nome)] = [str(s) for s in sinonimos or []]
    return skills


def _cv(nome: str) -> str:
    caminho = CURRICULO / nome
    if not caminho.exists():
        return ""
    texto = caminho.read_text(encoding="utf-8")
    return "" if "SUBSTITUA ESTE ARQUIVO" in texto else texto


def carregar() -> Config:
    return Config(
        empresas=carregar_empresas(),
        filtros=_ler(CONFIG / "filtros.yaml"),
        skills=carregar_skills(),
        cv={k: v for k, v in {"pt": _cv("cv_pt.md"), "en": _cv("cv_en.md")}.items() if v},
    )
