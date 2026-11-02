$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontend = Join-Path $root 'frontend'
$frontendModules = Join-Path $frontend 'node_modules'
$apiUrl = 'http://127.0.0.1:5000'
$webUrl = 'http://127.0.0.1:5173'

function Assert-ReadyToRun {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "The existing virtual environment is missing: $python`nCreate it and install backend\requirements.txt before starting ExoAtlas."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendModules 'vite\bin\vite.js') -PathType Leaf)) {
        throw "Frontend packages are missing under $frontendModules`nRun npm install in the frontend folder before starting ExoAtlas."
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'Node.js and npm must be installed and available on PATH.'
    }

    $requiredFiles = @(
        'data/processed/planets_application.csv',
        'data/processed/clustering_features_with_temp.csv',
        'data/metadata/cluster_profiles.json',
        'data/cluster_validation/cluster_validation_report.json',
        'data/cluster_experiments/clustering_report.json',
        'artifacts/preprocessing/scaler_with_temp.joblib',
        'artifacts/clustering/model_registry.json',
        'artifacts/clustering/kmeans_with_temp_k4.joblib'
    )
    $missingFiles = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf) })
    if ($missingFiles.Count -gt 0) {
        throw "Prepared ExoAtlas data is incomplete:`n - $($missingFiles -join "`n - ")`nRun the approved offline data preparation steps first."
    }

    & $python -c 'import flask, joblib, numpy, pandas, sklearn' 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependencies are missing from the existing virtual environment.`nRun: .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt"
    }
}

function Get-ListenerPids([int] $port) {
    $connections = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    return @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-BackendReady {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/api/health" -TimeoutSec 2
        return ($health.service -eq 'exoatlas-api' -and $health.status -eq 'ok' -and $health.data_ready -eq $true)
    } catch {
        return $false
    }
}

function Test-FrontendReady {
    try {
        $page = Invoke-WebRequest -Uri "$webUrl/" -TimeoutSec 2 -UseBasicParsing
        return ($page.StatusCode -eq 200 -and $page.Content -match '@vite/client' -and $page.Content -match 'id=["'']root["'']')
    } catch {
        return $false
    }
}

function Resolve-Port([int] $port, [string] $name, [scriptblock] $probe) {
    $pids = @(Get-ListenerPids $port)
    if ($pids.Count -eq 0) {
        Write-Host "$name`: port $port is available."
        return 'start'
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(8)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (& $probe) {
            Write-Host "$name`: reusing the ready service on port $port."
            return 'ready'
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$name`: port $port is occupied by process(es) $($pids -join ', '), but the listener did not identify as a ready ExoAtlas service. No process was stopped. Close the conflicting service or choose another port."
}

function Wait-Service([string] $name, [scriptblock] $probe, [int] $seconds = 60) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (& $probe) {
            Write-Host "$name is ready."
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$name did not become ready within $seconds seconds. Check its visible command window for the startup error."
}

try {
    Assert-ReadyToRun

    $backendState = Resolve-Port 5000 'Flask API' { Test-BackendReady }
    $frontendState = Resolve-Port 5173 'Vite frontend' { Test-FrontendReady }

    if ($backendState -eq 'start') {
        $backendCommand = "title ExoAtlas Backend && `"$python`" -m flask --app backend.app run --debug --host 127.0.0.1 --port 5000"
        Start-Process -FilePath $env:ComSpec -WorkingDirectory $root -WindowStyle Normal -ArgumentList @('/k', $backendCommand) | Out-Null
        Write-Host 'Started Flask API in a separate visible command window.'
    }
    if ($frontendState -eq 'start') {
        $frontendCommand = 'title ExoAtlas Frontend && npm run dev -- --host 127.0.0.1 --strictPort'
        Start-Process -FilePath $env:ComSpec -WorkingDirectory $frontend -WindowStyle Normal -ArgumentList @('/k', $frontendCommand) | Out-Null
        Write-Host 'Started Vite frontend in a separate visible command window.'
    }

    Wait-Service 'Flask API' { Test-BackendReady }
    Wait-Service 'Vite frontend' { Test-FrontendReady }
    Start-Process $webUrl | Out-Null
    Write-Host "ExoAtlas is open at $webUrl"
} catch {
    [Console]::Error.WriteLine("ExoAtlas startup failed: $($_.Exception.Message)")
    exit 1
}
