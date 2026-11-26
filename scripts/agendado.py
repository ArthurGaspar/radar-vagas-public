"""Ponto de entrada do Agendador de Tarefas do Windows.

Roda `python -m vagas run` sem janela (via pythonw.exe) e grava toda a saída
em logs/radar.log. Instalação da tarefa: scripts/instalar_tarefa.ps1.
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "logs" / "radar.log"
LIMITE_LOG = 2_000_000  # bytes; acima disso o log atual vira radar.log.1


def main():
    os.chdir(RAIZ)
    sys.path.insert(0, str(RAIZ))
    LOG.parent.mkdir(exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > LIMITE_LOG:
        LOG.replace(LOG.with_suffix(".log.1"))

    with open(LOG, "a", encoding="utf-8") as log:
        # pythonw não tem console: sem isso, print() some e erros passam batido.
        sys.stdout = sys.stderr = log
        print(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====", flush=True)
        try:
            from vagas.__main__ import main as radar
            sys.argv = ["vagas", "run"]
            radar()
        except SystemExit:
            pass
        except Exception:
            traceback.print_exc()
        log.flush()


if __name__ == "__main__":
    main()
