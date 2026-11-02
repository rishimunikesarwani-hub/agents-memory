param(
    [ValidateRange(1,4)][int]$Stage = 1,
    [ValidateSet('per_thread','per_invocation','stateless')][string]$Mode = 'per_thread'
)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
$sessionPath = Join-Path $projectPath 'runs\demo-session.json'
function Invoke-Memory {
    param([string[]]$CliArguments)
    $output = & $pythonPath -m user_memory @CliArguments
    if ($LASTEXITCODE -ne 0) { throw 'The memory command failed. Review the configuration and service status.' }
    return ($output -join "`n" | ConvertFrom-Json)
}
if ($Stage -eq 1) {
    $session = [pscustomobject]@{org='demo-day'; user=('session-' + [guid]::NewGuid().ToString('N')); thread='preferences'}
    $session | ConvertTo-Json | Set-Content -LiteralPath $sessionPath -Encoding UTF8
} elseif (Test-Path -LiteralPath $sessionPath) {
    $session = Get-Content -Raw -LiteralPath $sessionPath | ConvertFrom-Json
} else {
    throw 'Run Stage 1 before the later stages.'
}
$identity = @('--org',$session.org,'--user',$session.user,'--thread',$session.thread)
$previousStrategy = $env:MEMORY_LLM_SYNC_STRATEGY
$previousInterval = $env:MEMORY_LLM_EVERY_N_HUMANS
if ($Stage -eq 4) {
    $env:MEMORY_LLM_SYNC_STRATEGY = 'interval'
    $env:MEMORY_LLM_EVERY_N_HUMANS = '1000'
    Write-Output 'Demo extraction setting: interval=1000. This isolates worker conversation memory.'
} else {
    $env:MEMORY_LLM_SYNC_STRATEGY = 'every_turn'
    Write-Output 'Demo extraction setting: every_turn. Each command starts a separate application process.'
}
try {
    if ($Stage -eq 1) {
        $before = Invoke-Memory -CliArguments (@('profile') + $identity)
        if ($before.facts.Count -ne 0) { throw 'Expected a new profile.' }
        $turn = Invoke-Memory -CliArguments (@('turn','I prefer dark mode and US English.','--message-id','preference-1') + $identity)
        if ($turn.trace.memory_update -ne 'saved') { throw 'Memory was not saved.' }
        $profile = Invoke-Memory -CliArguments (@('profile') + $identity)
        $profile | ConvertTo-Json -Depth 12
    } elseif ($Stage -eq 2) {
        $parent = Invoke-Memory -CliArguments (@('inspect') + $identity)
        $worker = Invoke-Memory -CliArguments (@('inspect','--worker') + $identity)
        $profile = Invoke-Memory -CliArguments (@('profile') + $identity)
        if ($parent.messages.Count -lt 2 -or $worker.messages.Count -lt 2 -or $profile.facts.Count -lt 1) {
            throw 'Restart restoration did not return the expected records.'
        }
        [pscustomobject]@{parent_messages=$parent.messages.Count; worker_messages=$worker.messages.Count;
                         restored_facts=$profile.facts.Count; user=$session.user} | ConvertTo-Json
    } elseif ($Stage -eq 3) {
        $turn = Invoke-Memory -CliArguments (@('turn','Correction: use light mode instead of dark mode. Keep US English.',
                                              '--message-id','preference-2') + $identity)
        if ($turn.trace.memory_update -ne 'saved') { throw 'The correction was not saved.' }
        Invoke-Memory -CliArguments (@('profile') + $identity) | ConvertTo-Json -Depth 12
    } else {
        $billingUser = $session.user + '-' + $Mode
        $billing = @('--org',$session.org,'--user',$billingUser,'--thread','billing',
                     '--worker-mode',$Mode,'--context-mode','latest_only')
        $turns = @('I was charged twice.',"I'm on the Pro plan.",'I want a refund.')
        $rows = @()
        for ($i=0; $i -lt $turns.Count; $i++) {
            $out = Invoke-Memory -CliArguments (@('turn',$turns[$i],'--message-id',('billing-' + ($i+1))) + $billing)
            $rows += [pscustomobject]@{turn=$i+1; mode=$Mode; supplied=($out.trace.supplied_message_ids -join ',');
                                      before_reply=$out.trace.pre_reply_count; known=($out.trace.known | ConvertTo-Json -Compress);
                                      answer=$out.answer}
        }
        $rows | Format-Table turn,mode,supplied,before_reply,known -AutoSize
        $rows | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath ('runs\demo-billing-' + $Mode + '-summary.json') -Encoding UTF8
    }
} finally {
    if ($null -eq $previousStrategy) { Remove-Item Env:MEMORY_LLM_SYNC_STRATEGY -ErrorAction SilentlyContinue }
    else { $env:MEMORY_LLM_SYNC_STRATEGY = $previousStrategy }
    if ($null -eq $previousInterval) { Remove-Item Env:MEMORY_LLM_EVERY_N_HUMANS -ErrorAction SilentlyContinue }
    else { $env:MEMORY_LLM_EVERY_N_HUMANS = $previousInterval }
}
