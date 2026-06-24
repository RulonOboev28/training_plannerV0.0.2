# Build portable Windows folder with exe
# Run from project root:  .\scripts\build_release.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$AppName = "TrainingPlanConstructor"

Write-Host "==> Installing build dependencies..."
python -m pip install -r requirements.txt -q
python -m pip install -r requirements-build.txt -q

Write-Host "==> Generating demo plan..."
$demoDir = Join-Path $Root "build\demo"
New-Item -ItemType Directory -Force -Path $demoDir | Out-Null
$env:PYTHONPATH = $Root
python (Join-Path $Root "scripts\generate_demo_mesocycle_tplan.py") | Out-Null
$desktopPlan = Join-Path $env:USERPROFILE "Desktop\mesocycle_obem_skorost_tehnika.tplan"
$demoPlan = Join-Path $demoDir "mesocycle_obem_skorost_tehnika.tplan"
if (Test-Path $desktopPlan) {
    Copy-Item -Force $desktopPlan $demoPlan
    Write-Host "    Demo copied to build\demo"
} else {
    Write-Warning "Demo plan not found on Desktop; building without demo/*.tplan"
}

Write-Host "==> Running PyInstaller..."
python -m PyInstaller --noconfirm --clean (Join-Path $Root "build\training_constructor.spec")

$dist = Join-Path $Root ("dist\" + $AppName)
if (-not (Test-Path $dist)) {
    throw "Build failed: dist folder was not created"
}

$exe = Join-Path $dist ($AppName + ".exe")
Write-Host ""
Write-Host "Done: $dist"
Write-Host "Run:  $exe"
