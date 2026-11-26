"""Score de compatibilidade currículo × vaga, no estilo ATS (sem IA).

1. Detecta o idioma da vaga e escolhe o currículo PT ou EN.
2. Acha na vaga os termos do dicionário (config/skills.yaml), já unificando
   sinônimos ("k8s" = "kubernetes").
3. Cada termo ganha um peso pela seção onde aparece:
     título 1.5 · requisitos/texto geral 1.0 · diferenciais 0.5 · benefícios 0
4. Score = peso dos termos que também estão no currículo / peso total.
"""

import re
from dataclasses import dataclass, field

from .texto import compilar, normalizar

PESO_TITULO, PESO_PADRAO, PESO_DIFERENCIAL = 1.5, 1.0, 0.5
MIN_TERMOS_CONFIAVEL = 4

_CABECALHO_DIFERENCIAL = compilar([
    "nice to have", "nice to haves", "bonus", "bonus points", "preferred", "preferred qualifications",
    "pluses", "a plus", "it's a plus", "desejavel", "desejaveis", "diferencial", "diferenciais",
    "sera um plus", "seria um plus", "sera um diferencial", "conhecimentos desejaveis", "deseable",
    "deseables", "valorizado", "valoramos", "extra points", "would be great", "good to have",
])
_CABECALHO_BENEFICIOS = compilar([
    "benefits", "beneficios", "perks", "what we offer", "o que oferecemos", "oferecemos",
    "compensation", "remuneracao", "salary", "salario", "about us", "sobre nos", "sobre a empresa",
    "equal opportunity", "eeo",
])
_CABECALHO_REQUISITOS = compilar([
    "requirements", "requisitos", "qualifications", "qualificacoes", "what you'll need", "what you need",
    "what we're looking for", "what we are looking for", "must have", "must haves", "you have",
    "about you", "o que esperamos", "o que buscamos", "required", "requerimientos", "responsibilities",
    "responsabilidades", "atribuicoes", "what you'll do", "o que voce vai fazer", "your role",
])

_PT = {"voce", "nao", "com", "uma", "os", "dos", "das", "em", "nossa", "nosso", "seu", "sua",
       "atuar", "vaga", "conhecimento", "experiencia", "sera", "sao", "tambem", "pessoa"}
_ES = {"y", "el", "los", "las", "del", "con", "nuestro", "nuestra", "conocimiento", "trabajo",
       "usted", "tu", "somos", "equipo", "buscamos", "experiencia", "tambien", "persona"}
_EN = {"the", "and", "you", "with", "to", "of", "for", "our", "we", "will", "experience",
       "your", "is", "are", "team", "work"}


@dataclass
class Resultado:
    score: int | None             # None = sem currículo ou vaga sem nenhum termo conhecido
    idioma: str                   # pt | en | es
    cv: str | None                # pt | en (qual currículo mandar)
    batem: list[str] = field(default_factory=list)
    faltam: list[str] = field(default_factory=list)
    poucos_termos: bool = False


def idioma(texto: str) -> str:
    palavras = re.findall(r"[a-z]+", normalizar(texto[:4000]))
    contagem = {
        "pt": sum(p in _PT for p in palavras),
        "es": sum(p in _ES for p in palavras),
        "en": sum(p in _EN for p in palavras),
    }
    return max(contagem, key=contagem.get) if any(contagem.values()) else "en"


class Matcher:
    def __init__(self, skills: dict[str, list[str]], cvs: dict[str, str]):
        self.padroes = {nome: compilar(sinonimos, simbolos=True) for nome, sinonimos in skills.items()}
        self.cvs = cvs
        self.skills_cv = {lingua: self._achar(normalizar(texto)) for lingua, texto in cvs.items()}

    def _achar(self, texto_normalizado: str) -> set[str]:
        return {nome for nome, p in self.padroes.items() if p and p.search(texto_normalizado)}

    def _pesos(self, titulo: str, descricao: str) -> dict[str, float]:
        pesos: dict[str, float] = {nome: PESO_TITULO for nome in self._achar(normalizar(titulo))}
        peso_secao = PESO_PADRAO
        for linha in descricao.splitlines():
            n = normalizar(linha)
            if not n:
                continue
            # Linha curta que COMEÇA com um cabeçalho muda a seção atual
            # ("Nice to have:" muda; "Experience with X (preferred)" não).
            inicio = n.lstrip("-•*·#: ")
            if len(n) <= 60:
                if _CABECALHO_DIFERENCIAL.match(inicio):
                    peso_secao = PESO_DIFERENCIAL
                elif _CABECALHO_BENEFICIOS.match(inicio):
                    peso_secao = 0.0
                elif _CABECALHO_REQUISITOS.match(inicio):
                    peso_secao = PESO_PADRAO
            if peso_secao == 0.0:
                continue
            for nome in self._achar(n):
                pesos[nome] = max(pesos.get(nome, 0.0), peso_secao)
        return pesos

    def avaliar(self, titulo: str, descricao: str) -> Resultado:
        lingua = idioma(descricao or titulo)
        cv = "pt" if lingua == "pt" else "en"
        if cv not in self.cvs:
            cv = next(iter(self.cvs), None)
        if cv is None:
            return Resultado(score=None, idioma=lingua, cv=None)

        pesos = self._pesos(titulo, descricao)
        if not pesos:
            return Resultado(score=None, idioma=lingua, cv=cv, poucos_termos=True)

        meus = self.skills_cv[cv]
        ordem = sorted(pesos, key=lambda n: (-pesos[n], n.lower()))
        total = sum(pesos.values())
        obtido = sum(pesos[n] for n in ordem if n in meus)
        return Resultado(
            score=round(100 * obtido / total),
            idioma=lingua,
            cv=cv,
            batem=[n for n in ordem if n in meus],
            faltam=[n for n in ordem if n not in meus],
            poucos_termos=len(pesos) < MIN_TERMOS_CONFIAVEL,
        )
