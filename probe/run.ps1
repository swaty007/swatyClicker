# Run a probe script elevated via the MyClicker-Probe scheduled task and print its output.
# Usage: .\run.ps1 test_f12.py [args...]
param([Parameter(Mandatory)][string]$Script, [Parameter(ValueFromRemainingArguments)][string[]]$ScriptArgs)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$last = Join-Path $here "results\last_run.txt"
@{ script = $Script; args = @($ScriptArgs) } | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $here "job.json")
Remove-Item $last -ErrorAction SilentlyContinue
schtasks /run /tn MyClicker-Probe | Out-Null
for ($i = 0; $i -lt 600; $i++) {
    Start-Sleep -Milliseconds 500
    if ((Test-Path $last) -and (Select-String -Path $last -Pattern '^EXIT ' -Quiet)) { break }
}
Get-Content $last -Encoding utf8
