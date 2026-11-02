param([switch]$Models)
$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$previousBytecodeSetting = [Environment]::GetEnvironmentVariable('PYTHONDONTWRITEBYTECODE', 'Process')
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location -LiteralPath $labRoot
try {
    New-Item -ItemType Directory -Path (Join-Path $labRoot 'runs\verification') -Force | Out-Null
    py -X utf8 -B -m pytest --junitxml=runs/verification/tests.xml
    if ($LASTEXITCODE -ne 0) { throw 'Behavior tests failed.' }
    if ($Models) { py -X utf8 -B src/experiment.py --models }
    else { py -X utf8 -B src/experiment.py }
    if ($LASTEXITCODE -ne 0) { throw 'Experiment failed.' }
    py -X utf8 -B ops/build_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Demo generation failed.' }
    Write-Output (Join-Path $labRoot 'runs\demo.html')
}
finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE', $previousBytecodeSetting, 'Process')
}
