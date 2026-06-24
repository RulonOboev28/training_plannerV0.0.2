# Publish to GitHub: training_plannerV0.0.2
# Run:  .\scripts\publish_github.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$RepoName = "training_plannerV0.0.2"
$Gh = "$env:TEMP\gh-cli\bin\gh.exe"
if (-not (Test-Path $Gh)) {
    $GhZip = "$env:TEMP\gh.zip"
    $GhDir = "$env:TEMP\gh-cli"
    Invoke-WebRequest -Uri "https://github.com/cli/cli/releases/download/v2.67.0/gh_2.67.0_windows_amd64.zip" -OutFile $GhZip -UseBasicParsing
    Expand-Archive -Path $GhZip -DestinationPath $GhDir -Force
}

& $Gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub login required. A browser window will open."
    Write-Host "Enter the one-time code shown below at https://github.com/login/device"
    Start-Process "https://github.com/login/device"
    & $Gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key
}

$desc = "Конструктор тренировочного плана v0.0.2: иерархия, .tplan, демо-мезоцикл, exe, сводка нагрузки"
& $Gh repo view "RulonOboev28/$RepoName" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Gh repo create $RepoName --public --description $desc --source . --remote origin --push
} else {
    git push -u origin main --tags
}

Write-Host ""
Write-Host "Published: https://github.com/RulonOboev28/$RepoName"
