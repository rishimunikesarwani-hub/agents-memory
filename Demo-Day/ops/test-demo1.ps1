param([switch]$Postgres, [switch]$Live)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run uv sync --extra dev before testing.'
}
& $pythonPath -c "from user_memory.config import Settings; Settings.from_env()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Child processes do not inherit dotenv values loaded in a different Python process.
# The test fixture loads this project's .env itself.
$backend = if ($Postgres) { 'postgres' } else { 'memory' }
$reportPath = 'runs/demo1-' + $backend + '.json'
& $pythonPath -m pytest tests --backend $backend --json-report --json-report-file $reportPath -q
$testResult = $LASTEXITCODE
$testReport = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
if ($Postgres -and $testReport.summary.skipped -gt 0 -and $testResult -eq 0) {
    $testResult = 2
}
if ($Live -and $testResult -eq 0) {
    $env:RUN_LIVE_OPENAI = '1'
    try {
        & $pythonPath -m pytest evals -q --json-report --json-report-file runs/demo1-live.json
        if ($LASTEXITCODE -ne 0) { $testResult = $LASTEXITCODE }
    } finally {
        Remove-Item Env:RUN_LIVE_OPENAI
    }
}
& $pythonPath ops/acceptance_report.py
if ($LASTEXITCODE -ne 0 -and $testResult -eq 0) { $testResult = 2 }
exit $testResult
