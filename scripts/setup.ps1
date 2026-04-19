param(
    [string]$StellarisUserDir = "",
    [string]$StellarisInstallDir = "G:\SteamLibrary\steamapps\common\Stellaris",
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot | Split-Path -Parent

Write-Host ""
Write-Host "============================================="
Write-Host "  STELLARIS OVERMIND - First-Time Setup"
Write-Host "============================================="
Write-Host ""

# --- Find Stellaris ---
if (-not $StellarisUserDir) {
    @(
        "$env:USERPROFILE\OneDrive\Documents\Paradox Interactive\Stellaris",
        "$env:USERPROFILE\Documents\Paradox Interactive\Stellaris"
    ) | ForEach-Object { if ((Test-Path $_) -and -not $StellarisUserDir) { $StellarisUserDir = $_ } }
}
if (-not $StellarisUserDir -or -not (Test-Path $StellarisUserDir)) {
    Write-Error "Cannot find Stellaris user data. Use -StellarisUserDir."
    exit 1
}

$saveDir       = Join-Path $StellarisUserDir "save games"
$modDir        = Join-Path $StellarisUserDir "mod"
$modTarget     = Join-Path $modDir "stellaris_overmind"
$modDescTarget = Join-Path $modDir "stellaris_overmind.mod"
$modSource     = Join-Path $projectRoot "mod\stellaris_overmind"
$bridgeDir     = Join-Path $modSource "ai_bridge"

Write-Host "Stellaris dir: $StellarisUserDir"
Write-Host "Save dir:      $saveDir"
Write-Host ""

# --- Step 1: Python ---
Write-Host "--- Step 1: Python ---"
if (-not $SkipPython) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $ver = python --version 2>&1
        Write-Host "  Found: $ver"
        Push-Location $projectRoot
        python -m pip install -e ".[dev]" --quiet 2>&1 | Out-Null
        Pop-Location
        Write-Host "  Dependencies installed"
    } else {
        Write-Host "  WARNING: Python not found. Install from python.org"
    }
} else {
    Write-Host "  Skipped"
}

# --- Step 2: config.toml ---
Write-Host ""
Write-Host "--- Step 2: Config ---"
$configTarget = Join-Path $projectRoot "config.toml"
$configSource = Join-Path $projectRoot "config.example.toml"
if (-not (Test-Path $configTarget)) {
    $c = Get-Content $configSource -Raw
    $c = $c -replace [regex]::Escape("C:/Users/Fintz/OneDrive/Documents/Paradox Interactive/Stellaris"), ($StellarisUserDir -replace '\\','/')
    $c = $c -replace [regex]::Escape("G:/SteamLibrary/steamapps/common/Stellaris"), ($StellarisInstallDir -replace '\\','/')
    Set-Content $configTarget -Value $c -Encoding UTF8 -NoNewline
    Write-Host "  Created config.toml"
} else {
    Write-Host "  config.toml exists"
}

# --- Step 3: Bridge directory ---
Write-Host ""
Write-Host "--- Step 3: Bridge Dir ---"
if (-not (Test-Path $bridgeDir)) {
    New-Item -ItemType Directory -Path $bridgeDir -Force | Out-Null
}
Write-Host "  Bridge: $bridgeDir"

# --- Step 4: Link mod ---
Write-Host ""
Write-Host "--- Step 4: Link Mod ---"
if (-not (Test-Path $modTarget)) {
    cmd /c mklink /J "$modTarget" "$modSource" 2>&1 | Out-Null
    if (Test-Path $modTarget) {
        Write-Host "  Junction created"
    } else {
        Write-Host "  ERROR: Failed to create junction. Try as Admin."
        exit 1
    }
} else {
    Write-Host "  Mod link exists"
}

$absPath = ($modTarget -replace '\\','/')
$desc = "name=""Stellaris Overmind""`npath=""$absPath""`ntags={`n`t""AI""`n`t""Gameplay""`n}`npicture=""thumbnail.png""`nsupported_version=""v4.3.*"""
Set-Content $modDescTarget -Value $desc -Encoding UTF8 -NoNewline
Write-Host "  Mod descriptor updated"

# --- Step 5: Verify ---
Write-Host ""
Write-Host "--- Step 5: Verify ---"
$items = @(
    @("config.toml",       (Test-Path $configTarget)),
    @("Mod junction",      (Test-Path $modTarget)),
    @("Mod descriptor",    (Test-Path $modDescTarget)),
    @("Bridge dir",        (Test-Path $bridgeDir)),
    @("Events file",       (Test-Path "$modSource\events\overmind_events.txt")),
    @("Effects file",      (Test-Path "$modSource\common\scripted_effects\overmind_effects.txt")),
    @("Modifiers file",    (Test-Path "$modSource\common\static_modifiers\overmind_modifiers.txt")),
    @("Save games dir",    (Test-Path $saveDir)),
    @("Engine modules",    (Test-Path "$projectRoot\engine\game_loop.py"))
)
$allOk = $true
foreach ($item in $items) {
    $status = if ($item[1]) { "PASS" } else { "FAIL"; $allOk = $false }
    Write-Host "  $status  $($item[0])"
}

# --- Step 6: GPU ---
Write-Host ""
Write-Host "--- Step 6: GPU ---"
$gpu = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
if ($gpu) {
    Write-Host "  GPU: $gpu"
} else {
    Write-Host "  No NVIDIA GPU - use stub mode"
}

# --- Done ---
Write-Host ""
Write-Host "============================================="
if ($allOk) {
    Write-Host "  SETUP COMPLETE"
} else {
    Write-Host "  SETUP COMPLETE (with warnings)"
}
Write-Host "============================================="
Write-Host ""
Write-Host "NEXT STEPS:"
Write-Host ""
Write-Host "  1. ENABLE MOD: Launch Stellaris > Mods > Enable 'Stellaris Overmind'"
Write-Host ""
Write-Host "  2. START LLM (pick one):"
Write-Host "     docker compose up qwen -d          # Docker + GPU"
Write-Host "     ollama run qwen2.5:7b               # Ollama (easy)"
Write-Host "     # or skip (stub mode for testing)"
Write-Host ""
Write-Host "  3. START ENGINE:"
Write-Host "     cd $projectRoot"
Write-Host "     python -m engine                    # uses config.toml"
Write-Host "     python -m engine --provider stub    # no GPU needed"
Write-Host ""
Write-Host "  4. START GAME:"
Write-Host "     New game > match empire to config.toml"
Write-Host "     Settings > Autosave interval = 6 months"
Write-Host "     Play! Engine reads autosaves automatically."
Write-Host ""
