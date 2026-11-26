"""Filtros de título, nível e localização (config/filtros.yaml)."""

import re

from .modelos import Vaga
from .texto import compilar, contem, normalizar

ORDEM_NIVEIS = ("estagio", "senior_forte", "junior", "pleno", "senior")

# Nível informado pelo próprio ATS, usado só quando o título não diz nada.
# Chaves já normalizadas ("entry_level" e "Entry-level" viram "entry level").
HINTS = {
    "internship": "estagio", "intern": "estagio", "student": "estagio",
    "entry level": "junior", "associate": "junior", "trainee": "junior",
    "no experience required": "junior", "sin experiencia": "junior",
    "mid level": "pleno", "semi senior": "pleno",
    "senior": "senior", "senior level": "senior", "expert": "senior",
    "manager": "senior", "director": "senior", "executive": "senior",
}

_REMOTO = compilar(["remote", "remoto", "remota", "home office", "100% remoto", "anywhere",
                    "teletrabalho", "trabajo remoto", "work from home", "wfh"])
_HIBRIDO = compilar(["hybrid", "hibrido", "hibrida"])
_PRESENCIAL = compilar(["on site", "onsite", "presencial", "in office"])
# Códigos de requisição no título: "JR-186652", "R12345", "REQ-0042" (já normalizados).
_CODIGO_REQUISICAO = re.compile(r"(?<![a-z0-9])(?:jr|req|r)\s?\d{3,}(?![a-z0-9])")


class Filtros:
    def __init__(self, cfg: dict):
        t = cfg.get("titulo") or {}
        self.incluir = compilar(t.get("incluir") or [])
        self.excluir = compilar(t.get("excluir") or [])

        s = cfg.get("senioridade") or {}
        self.niveis_aceitos = set(s.get("aceitar") or ["junior", "pleno", "sem_nivel"])
        termos = s.get("termos") or {}
        self.niveis = [(n, compilar(termos.get(n) or [])) for n in ORDEM_NIVEIS]
        numerais = termos.get("numerais") or {"i": "junior", "ii": "pleno", "iii": "senior", "iv": "senior"}
        self.numerais = [(nivel, compilar([str(num)])) for num, nivel in numerais.items()]

        loc = cfg.get("localizacao") or {}
        self.presencial_ok = compilar(loc.get("presencial_ok") or [])
        self.remoto_ok = compilar(loc.get("remoto_ok") or [])
        self.remoto_bloquear = compilar(loc.get("remoto_bloquear") or [])
        self.aceitar_remoto_sem_regiao = loc.get("aceitar_remoto_sem_regiao", True)
        self.aceitar_local_desconhecido = loc.get("aceitar_local_desconhecido", True)

    def titulo_ok(self, titulo: str) -> bool:
        t = normalizar(titulo)
        return contem(self.incluir, t) and not contem(self.excluir, t)

    def nivel(self, titulo: str, hint: str | None = None) -> str:
        """estagio | junior | pleno | senior | sem_nivel"""
        t = _CODIGO_REQUISICAO.sub(" ", normalizar(titulo))
        for nome, padrao in self.niveis:
            if contem(padrao, t):
                return "senior" if nome == "senior_forte" else nome
        # Numerais por último: "I" também aparece como separador ("Empresa I Cargo").
        for nome, padrao in self.numerais:
            if contem(padrao, t):
                return nome
        return HINTS.get(normalizar(hint), "sem_nivel")

    def nivel_ok(self, nivel: str, estagio_ok: bool) -> bool:
        if nivel == "estagio":
            return estagio_ok
        return nivel in self.niveis_aceitos

    def local(self, vaga: Vaga) -> tuple[bool, str]:
        """(aceita?, rótulo para exibir)."""
        local = vaga.local.strip()
        # Região vem do local + trechos entre parênteses do título, ex:
        # "Software Engineer (Remote, LATAM)". O título inteiro não entra para
        # "Global Payments" não virar "global".
        entre_parenteses = " ".join(re.findall(r"[(\[]([^)\]]*)[)\]]", vaga.titulo))
        texto = normalizar(f"{local} | {entre_parenteses}")
        modelo = vaga.modelo
        if modelo is None:
            com_titulo = normalizar(f"{local} | {vaga.titulo}")
            if contem(_REMOTO, com_titulo):
                modelo = "remoto"
            elif contem(_HIBRIDO, com_titulo):
                modelo = "hibrido"
            elif contem(_PRESENCIAL, com_titulo):
                modelo = "presencial"

        # A cidade estruturada evita que "Campinas, São Paulo" (estado) passe como capital.
        em_sp = contem(self.presencial_ok, normalizar(vaga.cidade) if vaga.cidade else texto)
        regiao_ok = contem(self.remoto_ok, texto)
        bloqueado = contem(self.remoto_bloquear, texto)
        rotulo_modelo = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}.get(modelo, "modelo não informado")

        if modelo == "remoto":
            if regiao_ok or em_sp:
                return True, f"🌎 Remoto · {local}" if local else "🌎 Remoto"
            if bloqueado:
                return False, f"remoto restrito: {local}"
            return self.aceitar_remoto_sem_regiao, f"🌎 Remoto (região não informada){' · ' + local if local else ''}"
        if em_sp:
            return True, f"📍 {local} · {rotulo_modelo}"
        if modelo in ("hibrido", "presencial"):
            return False, f"{rotulo_modelo} fora da região aceita: {local}"
        if not local:
            return self.aceitar_local_desconhecido, "❔ Local não informado"
        if regiao_ok and not bloqueado:
            return True, f"🇧🇷 {local} · confirmar se é remoto"
        return False, f"fora da região: {local}"
