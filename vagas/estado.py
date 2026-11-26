"""Vagas já vistas, persistidas em JSON entre execuções.

No GitHub Actions esse arquivo vive num branch próprio ("estado"), sobrescrito
a cada execução com um único commit, para o histórico não crescer.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DIAS_PARA_ESQUECER = 60


class Estado:
    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.hoje = date.today().isoformat()
        self.vistos: dict[str, str] = {}   # id da vaga -> última data em que estava aberta
        self.fontes: dict[str, str] = {}   # fonte -> data da primeira leitura bem-sucedida
        self.ultima_execucao: datetime | None = None
        self.falhas: dict[str, int] = {}   # fonte -> execuções seguidas com erro
        if caminho.exists():
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            self.vistos = dados.get("vistos", {})
            self.fontes = dados.get("fontes", {})
            self.falhas = dados.get("falhas", {})
            if dados.get("ultima_execucao"):
                self.ultima_execucao = datetime.fromisoformat(dados["ultima_execucao"])

    def horas_desde_ultima(self) -> float | None:
        if self.ultima_execucao is None:
            return None
        return (datetime.now(timezone.utc) - self.ultima_execucao).total_seconds() / 3600

    def registrar_falhas(self, erros: dict[str, str], alertar_apos: int) -> dict[str, int]:
        """Atualiza a contagem de falhas seguidas e devolve as fontes que devem
        gerar alerta agora: ao atingir `alertar_apos` e depois a cada 24 falhas."""
        self.falhas = {k: self.falhas.get(k, 0) + 1 for k in erros}  # quem não falhou, zera
        return {k: n for k, n in self.falhas.items()
                if n == alertar_apos or (n > alertar_apos and (n - alertar_apos) % 24 == 0)}

    def fonte_nova(self, fonte: str) -> bool:
        """Fonte nunca lida antes: as vagas dela entram sem notificar."""
        return fonte not in self.fontes

    def registrar_fonte(self, fonte: str) -> None:
        self.fontes.setdefault(fonte, self.hoje)

    def ja_vista(self, id_vaga: str) -> bool:
        return id_vaga in self.vistos

    def marcar(self, id_vaga: str) -> None:
        self.vistos[id_vaga] = self.hoje

    def salvar(self) -> None:
        limite = (date.today() - timedelta(days=DIAS_PARA_ESQUECER)).isoformat()
        self.vistos = {k: v for k, v in self.vistos.items() if v >= limite}
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "versao": 1,
            "ultima_execucao": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fontes": self.fontes,
            "falhas": self.falhas,
            "vistos": self.vistos,
        }
        self.caminho.write_text(json.dumps(dados, sort_keys=True, separators=(",", ":")), encoding="utf-8")
