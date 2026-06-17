# Descarga e instala Python local si no hay ninguno disponible.
# Uso interno desde iniciar_servidor.bat

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root "venv\Scripts\python.exe"
$ToolsDir = Join-Path $Root "tools"
$DownloadsDir = Join-Path $ToolsDir "downloads"
$PythonVersion = "3.12.7"
$PythonDir = Join-Path $ToolsDir "python312"
$PythonExe = Join-Path $PythonDir "python.exe"
$InstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$InstallerPath = Join-Path $DownloadsDir "python-$PythonVersion-amd64.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "  >> $Message"
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Find-SystemPython {
    $candidates = @(
        @("py", @("-3.12")),
        @("py", @("-3.11")),
        @("py", @("-3.10")),
        @("python", @()),
        @("python3", @())
    )
    foreach ($item in $candidates) {
        $cmd = $item[0]
        $args = $item[1]
        if (-not (Test-Command $cmd)) { continue }
        try {
            $versionText = & $cmd @args -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
            if (-not $versionText) { continue }
            $parts = $versionText.Trim().Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                return @{ Command = $cmd; Args = $args }
            }
        } catch {}
    }
    return $null
}

function New-ProjectVenv([string]$BasePython, [string[]]$BaseArgs) {
    Write-Step "Creando entorno virtual en venv\ ..."
    $venvPath = Join-Path $Root "venv"
    if (Test-Path $venvPath) {
        Remove-Item -Recurse -Force $venvPath
    }
    & $BasePython @BaseArgs -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual."
    }
}

function Install-PortablePython {
    Write-Step "Descargando Python $PythonVersion (~25 MB, solo la primera vez)..."
    New-Item -ItemType Directory -Force -Path $DownloadsDir | Out-Null

    if (-not (Test-Path $InstallerPath)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerPath -UseBasicParsing
    }

    Write-Step "Instalando Python en tools\python312 (sin permisos de administrador)..."
    if (Test-Path $PythonDir) {
        Remove-Item -Recurse -Force $PythonDir
    }
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null

    $installArgs = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=0",
        "Include_test=0",
        "Include_launcher=0",
        "Include_pip=1",
        "AssociateFiles=0",
        "Shortcuts=0",
        "TargetDir=$PythonDir"
    )
    $proc = Start-Process -FilePath $InstallerPath -ArgumentList $installArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0 -or -not (Test-Path $PythonExe)) {
        throw "La instalacion de Python fallo (codigo $($proc.ExitCode))."
    }
}

if (Test-Path $VenvPython) {
    Write-Host "[OK] Entorno virtual listo."
    exit 0
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  ERP - Preparando Python"
Write-Host "============================================================"

$systemPython = Find-SystemPython
if ($systemPython) {
    Write-Step "Python del sistema encontrado ($($systemPython.Command))."
    New-ProjectVenv -BasePython $systemPython.Command -BaseArgs $systemPython.Args
} else {
    Write-Step "Python no detectado. Se descargara automaticamente."
    Install-PortablePython
    New-ProjectVenv -BasePython $PythonExe -BaseArgs @()
}

if (-not (Test-Path $VenvPython)) {
    throw "No se encontro venv\Scripts\python.exe tras la instalacion."
}

Write-Host ""
Write-Host "[OK] Python listo: $VenvPython"
exit 0
