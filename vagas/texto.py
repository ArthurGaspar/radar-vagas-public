"""Normalização de texto e casamento de termos como palavra inteira."""

import html
import re
import unicodedata

_SEPARADORES = re.compile(r"[-_/–—]+")
_ESPACOS = re.compile(r"\s+")
_ANTES, _DEPOIS = r"(?<![a-z0-9])", r"(?![a-z0-9])"
# Para skills, + e # contam como parte do termo: "c" não casa dentro de "c++".
# Nos filtros não, senão "staff" não casaria em "Staff+".
_ANTES_SIMB, _DEPOIS_SIMB = r"(?<![a-z0-9+#])", r"(?![a-z0-9+#])"


def normalizar(texto: str | None) -> str:
    """Minúsculo, sem acento, com hífen/barra/underscore virando espaço."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().replace("’", "'").replace("‘", "'")
    texto = _SEPARADORES.sub(" ", texto)
    return _ESPACOS.sub(" ", texto).strip()


def compilar(termos: list[str], simbolos: bool = False) -> re.Pattern | None:
    """Regex que casa qualquer um dos termos como palavra inteira.

    Os termos mais longos vêm primeiro para "full stack" ganhar de "stack".
    """
    normalizados = sorted({normalizar(t) for t in termos if t and normalizar(t)}, key=len, reverse=True)
    if not normalizados:
        return None
    corpo = "|".join(re.escape(t) for t in normalizados)
    antes, depois = (_ANTES_SIMB, _DEPOIS_SIMB) if simbolos else (_ANTES, _DEPOIS)
    return re.compile(f"{antes}(?:{corpo}){depois}")


def contem(padrao: re.Pattern | None, texto_normalizado: str) -> bool:
    return bool(padrao and padrao.search(texto_normalizado))


def html_para_texto(conteudo: str | None) -> str:
    """Converte HTML em texto preservando quebras de linha entre blocos.

    A quebra de linha importa: é ela que permite achar cabeçalhos como
    "Requisitos" ou "Nice to have" na hora de pesar os termos.
    """
    if not conteudo:
        return ""
    if "&lt;" in conteudo:  # Greenhouse entrega o HTML escapado
        conteudo = html.unescape(conteudo)
    conteudo = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", conteudo)
    conteudo = re.sub(r"(?i)<br\s*/?>", "\n", conteudo)
    conteudo = re.sub(r"(?i)<li[^>]*>", "\n- ", conteudo)
    conteudo = re.sub(r"(?i)</(p|div|li|h[1-6]|ul|ol|tr|section|strong|b)>", "\n", conteudo)
    conteudo = re.sub(r"<[^>]+>", " ", conteudo)
    conteudo = html.unescape(conteudo)
    linhas = (re.sub(r"[ \t\xa0]+", " ", linha).strip() for linha in conteudo.splitlines())
    return "\n".join(linha for linha in linhas if linha)
