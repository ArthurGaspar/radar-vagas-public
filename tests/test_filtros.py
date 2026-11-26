import pytest

from vagas.config import CONFIG, _ler
from vagas.filtros import Filtros
from vagas.modelos import Vaga


@pytest.fixture(scope="module")
def f():
    return Filtros(_ler(CONFIG / "filtros.yaml"))


def vaga(titulo="Software Engineer", local="", cidade="", modelo=None):
    return Vaga(id="x", fonte="x", ats="x", empresa="X", titulo=titulo, url="", local=local, cidade=cidade, modelo=modelo)


@pytest.mark.parametrize("titulo, esperado", [
    ("Software Engineer", True),
    ("Desenvolvedor(a) Full-Stack Pleno", True),
    ("Engenharia de Software JR", True),
    ("QA Automation Engineer", True),
    ("AI Engineer, Applied AI", True),
    ("Backend Developer (Python)", True),
    ("Account Executive, AI Native", False),       # excluir vence incluir
    ("Mechanical Engineer", False),
    ("Desenvolvimento Humano e Organizacional", False),
    ("Product Designer", False),
    ("Internal Auditor", False),                    # "intern" não casa em "internal"
])
def test_titulo(f, titulo, esperado):
    assert f.titulo_ok(titulo) is esperado


@pytest.mark.parametrize("titulo, nivel", [
    ("Software Engineer", "sem_nivel"),
    ("Junior Software Engineer", "junior"),
    ("Desenvolvedor Júnior/Pleno", "junior"),
    ("Desenvolvedor Pleno/Sênior", "pleno"),
    ("Engenharia de Software PL", "pleno"),
    ("Senior Backend Engineer", "senior"),
    ("Staff+ Software Engineer", "senior"),
    ("Associate Director, Engineering", "senior"),
    ("Coordenação de Engenharia de Software", "senior"),
    ("Pessoa Desenvolvedora Fullstack - Especialista I", "senior"),
    ("Software Engineer I", "junior"),
    ("Software Engineer II", "pleno"),
    ("Software Engineering Intern", "estagio"),
    ("Estágio em Desenvolvimento", "estagio"),
    ("New Grad Software Engineer", "junior"),
    ("JR-186652 Full stack Developer Senior", "senior"),             # JR-xxxx é código, não júnior
    ("Empresa X I Engenheiro de Dados Sênior I Remoto", "senior"),     # "I" separador
    ("Software Engineer III", "senior"),
    ("Desenvolvedor(a) Python I", "junior"),
])
def test_nivel(f, titulo, nivel):
    assert f.nivel(titulo) == nivel


def test_nivel_hint_so_quando_titulo_nao_diz(f):
    assert f.nivel("Software Engineer", "entry_level") == "junior"
    assert f.nivel("Senior Software Engineer", "entry_level") == "senior"


def test_estagio_so_em_empresa_liberada(f):
    assert f.nivel_ok("estagio", estagio_ok=True)
    assert not f.nivel_ok("estagio", estagio_ok=False)
    assert f.nivel_ok("sem_nivel", estagio_ok=False)
    assert not f.nivel_ok("senior", estagio_ok=True)


@pytest.mark.parametrize("v, aceita", [
    (vaga(local="Remote - Brazil", modelo="remoto"), True),
    (vaga(local="Remote, LATAM"), True),                              # modelo detectado no texto
    (vaga(titulo="Software Engineer (Remote, Brazil)", local="Remote"), True),
    (vaga(local="Remote - United States", modelo="remoto"), False),
    (vaga(local="Vietnam, Remote"), False),
    (vaga(local="São Paulo, SP, Brasil", modelo="hibrido"), True),
    (vaga(local="Barueri, SP", modelo="presencial"), True),
    (vaga(local="Campinas, São Paulo, Brasil", cidade="Campinas", modelo="hibrido"), False),
    (vaga(local="Rio de Janeiro, RJ, Brasil", modelo="presencial"), False),
    (vaga(local="Brazil"), True),                                     # modelo desconhecido: confirmar
    (vaga(local=""), True),                                           # local desconhecido
    (vaga(local="San Francisco, CA"), False),
    (vaga(titulo="Engineer, Global Payments", local="Tokyo"), False),  # "global" do título não conta
])
def test_local(f, v, aceita):
    assert f.local(v)[0] is aceita
