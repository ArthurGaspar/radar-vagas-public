from dataclasses import dataclass, field


@dataclass
class Empresa:
    nome: str
    ats: str
    slug: str
    estagio: bool = False
    busca: list[str] = field(default_factory=list)

    @property
    def chave(self) -> str:
        return f"{self.ats}:{self.slug}"


@dataclass
class Vaga:
    id: str                       # único entre execuções, ex: "greenhouse:stripe:123"
    fonte: str                    # chave da fonte que trouxe a vaga (empresa ou busca)
    ats: str
    empresa: str
    titulo: str
    url: str
    local: str = ""               # texto livre: "São Paulo, SP, Brasil", "Remote - LATAM"
    cidade: str = ""              # quando o ATS informa a cidade separada
    modelo: str | None = None     # "remoto" | "hibrido" | "presencial" | None
    publicada_em: str | None = None
    descricao: str = ""           # texto puro; vazio até `detalhar` ser chamado
    nivel_hint: str | None = None  # nível informado pelo próprio ATS, quando existe
    estagio_ok: bool = False
    extra: dict = field(default_factory=dict)  # dados que o adaptador precisa para detalhar
