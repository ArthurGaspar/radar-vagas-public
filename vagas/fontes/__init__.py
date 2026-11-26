"""Adaptadores de ATS.

Cada módulo expõe:
    listar(empresa)  -> list[Vaga]   lista barata das vagas abertas
    detalhar(vaga)   -> None         preenche descrição (e às vezes local/modelo);
                                     só é chamado para vagas novas que passaram
                                     nos filtros de título e nível
"""

from importlib import import_module

from ..modelos import Empresa, Vaga

ATS = (
    "greenhouse", "lever", "ashby", "workday", "smartrecruiters",
    "workable", "teamtailor", "recruitee", "gupy", "inhire",
)


def modulo(ats: str):
    if ats not in ATS:
        raise ValueError(f"ATS desconhecido: {ats!r} (opções: {', '.join(ATS)})")
    return import_module(f"{__name__}.{ats}")


def listar(empresa: Empresa) -> list[Vaga]:
    return modulo(empresa.ats).listar(empresa)


def detalhar(vaga: Vaga) -> None:
    # Portais de busca (getonbrd, remotar, himalayas) já trazem a descrição.
    if vaga.descricao or vaga.ats not in ATS:
        return
    mod = modulo(vaga.ats)
    if hasattr(mod, "detalhar"):
        mod.detalhar(vaga)


def nova(empresa: Empresa, id_vaga, **campos) -> Vaga:
    return Vaga(
        id=f"{empresa.chave}:{id_vaga}",
        fonte=empresa.chave,
        ats=empresa.ats,
        empresa=empresa.nome,
        estagio_ok=empresa.estagio,
        **campos,
    )


def modelo(valor) -> str | None:
    """Normaliza o modelo de trabalho dos vários formatos dos ATS."""
    v = str(valor or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    if not v or v in ("none", "unspecified", "null"):
        return None
    if "remot" in v or v in ("telecommute", "homeoffice"):
        return "remoto"
    if "hybrid" in v or "hibrid" in v or "híbrid" in v:
        return "hibrido"
    if "onsite" in v or "office" in v or "presencial" in v:
        return "presencial"
    return None
