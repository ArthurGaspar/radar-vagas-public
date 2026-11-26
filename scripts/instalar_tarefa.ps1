# Registra o radar no Agendador de Tarefas do Windows: de hora em hora, das
# 06:17 às 23:17, sem abrir janela. Rodar de novo substitui a tarefa existente.
#
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_tarefa.ps1
#
# Remover:  Unregister-ScheduledTask -TaskName "Radar de Vagas" -Confirm:$false

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = & python -c "import sys; print(sys.executable)"
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "pythonw.exe não encontrado ao lado de $python" }

$acao = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "`"$raiz\scripts\agendado.py`"" -WorkingDirectory $raiz

# Diário às 06:17, repetindo a cada 1h por 17h01min (última execução às 23:17).
$gatilho = New-ScheduledTaskTrigger -Daily -At "06:17"
$repeticao = New-ScheduledTaskTrigger -Once -At "06:17" `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 17 -Minutes 1)
$gatilho.Repetition = $repeticao.Repetition

$config = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Radar de Vagas" -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Radar de vagas: coleta vagas novas e notifica no Discord (radar-de-vagas)" -Force | Out-Null

$tarefa = Get-ScheduledTask -TaskName "Radar de Vagas"
$info = $tarefa | Get-ScheduledTaskInfo
Write-Output "Tarefa registrada. Estado: $($tarefa.State). Próxima execução: $($info.NextRunTime)"
Write-Output "Python: $pythonw"
