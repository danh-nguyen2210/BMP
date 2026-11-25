param([switch]$SatOnly)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = '.\.venv\Scripts\python.exe'
    $list = 'config/table7_large_person1.txt'
    $prefix = 'results/table7_large_person1'
    $stopFile = "${prefix}.stop"
    if (Test-Path -LiteralPath $stopFile) {
        Write-Host "Paused. Remove $stopFile to resume."
        return
    }
    $instances = Get-Content -LiteralPath $list
    $missing = @($instances | Where-Object { -not (Test-Path "data/$_.mtx") })
    if ($missing.Count -gt 0) {
        & $python -X utf8 -m src.downloader @missing
        foreach ($name in $missing) {
            if (-not (Test-Path "data/$name.mtx")) { throw "Missing matrix: $name" }
        }
    }
    $common = @('--instances-file', $list, '--timeout', '600', '--size-limit', '1000', '--stop-file', $stopFile)
    function Invoke-Batch($runner, $label, $options) {
        $stem = "${prefix}_${label}_600"
        & $python -X utf8 $runner @common @options --checkpoint "$stem.sqlite3" --output "$stem.csv"
        if ($LASTEXITCODE -ne 0) { throw "$runner exited with code $LASTEXITCODE" }
    }
    foreach ($amo in 'pairwise', 'sequential', 'product') {
        if (Test-Path -LiteralPath $stopFile) { return }
        # Preserve completed rows made by the previous build under their original settings.
        $previousBuild = '1baea4bc93d37dbcf29c9fe9b37ecfb67c5f065ae7d69082dd4092953a267ddc'
        Invoke-Batch 'run_benchmarks.py' $amo @('--table','7','--strategy','linear','--amo',$amo,'--memory-limit-gib','5','--reuse-uncapped-hash',$previousBuild,'--solvers','order-inc','order-iter','pairwise-inc','pairwise-iter')
    }
    if ($SatOnly -or (Test-Path -LiteralPath $stopFile)) { return }
    Invoke-Batch 'run_baselines.py' 'baselines' @('--threads','1','--solvers','cplex-cp','cplex-mip','gurobi')
    if (Test-Path -LiteralPath $stopFile) { return }
    Invoke-Batch 'run_cpsat.py' 'cpsat' @('--threads','1')
} finally {
    Pop-Location
}
