param([switch]$SatOnly)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = if (Test-Path -LiteralPath '.\.venv\Scripts\python.exe') { '.\.venv\Scripts\python.exe' } else { 'python' }
    $list = 'config/table7_large_person3.txt'
    $prefix = 'results/table7_large_person3'
    $stopFile = "${prefix}.stop"
    if (Test-Path -LiteralPath $stopFile) {
        Write-Host "Paused. Remove $stopFile to resume."
        return
    }
    $instances = @(Get-Content -LiteralPath $list | ForEach-Object { ($_ -split '#', 2)[0].Trim() } | Where-Object { $_ })
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
        Invoke-Batch 'run_benchmarks.py' $amo @('--table','7','--strategy','linear','--amo',$amo,'--memory-limit-gib','5','--solvers','order-inc','order-iter','pairwise-inc','pairwise-iter')
    }
    if ($SatOnly -or (Test-Path -LiteralPath $stopFile)) { return }
    Invoke-Batch 'run_baselines.py' 'baselines' @('--threads','1','--solvers','cplex-cp','cplex-mip','gurobi')
    if (Test-Path -LiteralPath $stopFile) { return }
    Invoke-Batch 'run_cpsat.py' 'cpsat' @('--threads','1')
} finally {
    Pop-Location
}
