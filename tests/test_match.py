from vagas.config import carregar_skills
from vagas.match import Matcher, idioma
from vagas.texto import html_para_texto

CV_EN = """
Software developer. TypeScript, Node.js, React, Python, PostgreSQL, Docker.
Built a RAG assistant with LangChain and embeddings. E2E tests with Playwright.
Languages: Portuguese (native), English (fluent), Spanish (advanced).
"""
CV_PT = "Desenvolvedor. TypeScript, Node.js, React, Python, Docker, Playwright. Inglês fluente."


def matcher():
    return Matcher(carregar_skills(), {"en": CV_EN, "pt": CV_PT})


def test_idioma():
    assert idioma("We are looking for an engineer to join our team and you will work with the product") == "en"
    assert idioma("Estamos buscando uma pessoa desenvolvedora para atuar com nosso time, você será") == "pt"
    assert idioma("Buscamos una persona para nuestro equipo de trabajo y el desarrollo de los productos") == "es"


def test_score_e_listas():
    descricao = "\n".join([
        "About the role",
        "Requirements",
        "- Strong TypeScript and React",
        "- Experience with Kubernetes",
        "Nice to have",
        "- Go",
        "- Playwright",
        "Benefits",
        "- Python lunch club",   # benefícios não contam
    ])
    r = matcher().avaliar("Frontend Engineer", descricao)
    assert r.cv == "en"
    assert set(r.batem) == {"TypeScript", "React", "Playwright"}
    assert r.faltam == ["Kubernetes"]       # "Go" só casa com "golang"/"go lang"
    # TypeScript 1 + React 1 + Playwright 0.5 de um total de 3.5
    assert r.score == round(100 * 2.5 / 3.5)


def test_sinonimos_unificam():
    r = matcher().avaliar("Engineer", "Requirements\n- k8s\n- Node\n- nodejs")
    assert "Kubernetes" in r.faltam and "Node.js" in r.batem
    assert r.faltam.count("Kubernetes") == 1


def test_vaga_pt_usa_cv_pt():
    r = matcher().avaliar("Desenvolvedor", "Requisitos\n- Experiência com React e você vai atuar com Node.js e AWS")
    assert r.cv == "pt"
    assert "AWS" in r.faltam


def test_c_nao_casa_dentro_de_cpp():
    m = Matcher({"C": ["linguagem c"], "C++": ["c++"]}, {"en": "I know C++"})
    assert m.skills_cv["en"] == {"C++"}


def test_sem_cv():
    r = Matcher(carregar_skills(), {}).avaliar("Engineer", "Python")
    assert r.score is None and r.cv is None


def test_html_preserva_linhas():
    t = html_para_texto("&lt;p&gt;&lt;strong&gt;Requirements&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;")
    assert t.splitlines() == ["Requirements", "- Python"]
