$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Resolve-PythonExe {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3 --version | Out-Null
            if ($LASTEXITCODE -eq 0) { return "py -3" }
        } catch {}
    }

    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $localPython) { return $localPython }

    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found -and $found.Source -notlike "*WindowsApps*python.exe") { return $found.Source }

    return $null
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Fichier .env cree. Renseigne TENANT_ID, CLIENT_ID et CLIENT_SECRET puis relance." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creation de l'environnement virtuel .venv..."
    $PythonExe = Resolve-PythonExe
    if (-not $PythonExe) {
        Write-Host "Python introuvable. Installe Python 3.12 ou corrige le PATH." -ForegroundColor Red
        exit 1
    }
    if ($PythonExe -eq "py -3") {
        & py -3 -m venv .venv
    } else {
        & $PythonExe -m venv .venv
    }
}

Write-Host "Installation / mise a jour des dependances..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Application disponible sur : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "CTRL+C pour arreter."
Write-Host ""

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
