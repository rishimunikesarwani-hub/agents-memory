$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectPath '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Output 'Existing .env preserved. No credentials changed.'
    exit 0
}
$randomBytes = New-Object byte[] 24
$generator = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $generator.GetBytes($randomBytes)
} finally {
    $generator.Dispose()
}
$databasePassword = [Convert]::ToBase64String($randomBytes).Replace('+','-').Replace('/','_').TrimEnd('=')
$templatePath = Join-Path $projectPath '.env.example'
$content = [IO.File]::ReadAllText($templatePath)
$content = $content.Replace('POSTGRES_PASSWORD=' + "`n", 'POSTGRES_PASSWORD=' + $databasePassword + "`n")
$content = $content.Replace('POSTGRES_PASSWORD=' + "`r`n", 'POSTGRES_PASSWORD=' + $databasePassword + "`r`n")
$content = $content.Replace('YOUR_LOCAL_PASSWORD', $databasePassword)
[IO.File]::WriteAllText($envPath, $content, (New-Object Text.UTF8Encoding $false))
Write-Output 'Created excluded .env with a random database password. OPENAI_API_KEY remains blank.'
