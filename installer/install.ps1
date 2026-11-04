# SimRCL installer for Windows. Run it through INSTALL.bat (double-click).
#
# What it does:
#   1. Finds every Cinema 4D 2026+ preferences folder in %APPDATA%\Maxon.
#   2. Moves earlier copies (plugins\SimRCL, and the script versions library\scripts\SimRCL / SimRS) into a
#      dated backup, so only one SimRCL is loaded (nothing is deleted).
#   3. Copies the SimRCL plugin folder from this archive into plugins.
#   4. Checks for Python 3 and installs usd-core into SimRCL's private folder, so the first import is fast.
#
# Options: -SkipRuntime (do not touch usd-core), -AppData <dir> / -LocalAppData <dir> (for tests).
param(
    [switch]$SkipRuntime,
    [string]$AppData = $env:APPDATA,
    [string]$LocalAppData = $env:LOCALAPPDATA
)

# Continue: with Stop, Windows PowerShell 5.1 turns any stderr line of python or pip into a fatal error.
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Here 'SimRCL'
# The data folders keep the project's first name, so downloads and settings of older versions are found.
$DataName = 'SRC by Deadwall'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
# Where earlier versions lived: the plugin folder, and the scripts folder of the script releases up to 1.1.0.
$OldPlaces = @('plugins\SimRCL', 'library\scripts\SimRCL', 'library\scripts\SimRS')
$Probe = 'import sys; sys.path.insert(0, sys.argv[1]); from pxr import Usd; Usd.Stage.CreateInMemory()'

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }

function Find-PrefsFolders {
    $maxon = Join-Path $AppData 'Maxon'
    if (-not (Test-Path $maxon)) { return @() }
    # "Maxon Cinema 4D 2026_1ABCDC12"; the _c / _p / _w / _x siblings belong to the command line and Team Render.
    return @(Get-ChildItem $maxon -Directory | Where-Object {
        $_.Name -match '^Maxon Cinema 4D (\d{4})[^_]*_[0-9A-Fa-f]{8}$' -and [int]$Matches[1] -ge 2026
    })
}

function Backup-OldCopies([System.IO.DirectoryInfo]$Prefs) {
    foreach ($place in $OldPlaces) {
        $old = Join-Path $Prefs.FullName $place
        if (-not (Test-Path $old)) { continue }
        # Outside the Cinema 4D folders: a copy left there would load (or show in the menu) twice.
        $leaf = ($place -replace '\\', '_')
        $backup = Join-Path (Join-Path (Join-Path $AppData $DataName) 'backup') ("{0}\{1}_{2}" -f $Prefs.Name, $leaf, $Stamp)
        New-Item -ItemType Directory -Force -Path (Split-Path $backup) -ErrorAction Stop | Out-Null
        Move-Item -LiteralPath $old -Destination $backup -ErrorAction Stop
        Say ("  previous {0} moved to {1}" -f $place, $backup)
    }
}

function Install-Into([System.IO.DirectoryInfo]$Prefs) {
    $plugins = Join-Path $Prefs.FullName 'plugins'
    New-Item -ItemType Directory -Force -Path $plugins -ErrorAction Stop | Out-Null
    Backup-OldCopies $Prefs
    Copy-Item -LiteralPath $Source -Destination $plugins -Recurse -ErrorAction Stop
    Say ("  installed into {0}" -f (Join-Path $plugins 'SimRCL')) 'Green'
}

function Find-Python {
    foreach ($candidate in @(@('py', '-3'), @('python3'), @('python'))) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $rest = @($candidate | Select-Object -Skip 1)
        # The Microsoft Store stub named python.exe prints nothing useful, so the version text is checked.
        $version = (& $exe @rest --version 2>&1 | Out-String)
        if ($LASTEXITCODE -eq 0 -and $version -match 'Python 3') { return ,$candidate }
    }
    return $null
}

function Install-Runtime {
    $python = Find-Python
    if ($null -eq $python) {
        Say 'Python 3 was not found. SimRCL needs it to read USD files:' 'Yellow'
        Say '  install it from https://www.python.org/downloads/ with "Add python.exe to PATH" ticked,' 'Yellow'
        Say '  then run INSTALL.bat again (or just import: SimRCL sets itself up on the first import).' 'Yellow'
        return
    }
    $exe = $python[0]; $rest = @($python | Select-Object -Skip 1)
    $target = Join-Path $LocalAppData "$DataName\usd_runtime\usd_core"
    & $exe @rest -I -c $Probe $target 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Say '  USD runtime: already installed' 'Green'; return }
    Say '  installing usd-core (about 30 MB, needs internet, once)...'
    & $exe @rest -m pip install usd-core --target $target --upgrade --disable-pip-version-check --no-warn-script-location -q
    & $exe @rest -I -c $Probe $target 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Say '  USD runtime: ready' 'Green' }
    else { Say '  usd-core did not install; SimRCL will try again on the first import.' 'Yellow' }
}

Say 'SimRCL by Dead_wall - installer' 'Cyan'
if (-not (Test-Path (Join-Path $Source 'SimRCL.pyp'))) {
    Say 'The SimRCL folder is missing next to INSTALL.bat. Unpack the whole archive first.' 'Red'
    exit 1
}
$folders = Find-PrefsFolders
if ($folders.Count -eq 0) {
    Say 'No Cinema 4D 2026 preferences folder found in %APPDATA%\Maxon.' 'Red'
    Say 'Start Cinema 4D once (it creates the folder) and run INSTALL.bat again, or copy the SimRCL folder by hand:' 'Red'
    Say '  Cinema 4D > Edit > Preferences > Open Preferences Folder > plugins' 'Red'
    exit 1
}
$failed = 0
foreach ($prefs in $folders) {
    Say ("Cinema 4D preferences: {0}" -f $prefs.Name)
    try { Install-Into $prefs }
    catch { $failed++; Say ("  could not install here: {0}" -f $_.Exception.Message) 'Red' }
}
if ($failed -eq $folders.Count) { exit 1 }
if (-not $SkipRuntime) { Install-Runtime }
if (Get-Process -Name 'Cinema 4D' -ErrorAction SilentlyContinue) {
    Say 'Cinema 4D is running: restart it, plugins load at start-up.' 'Yellow'
}
Say ''
Say 'Done. In Cinema 4D: Extensions > SimRCL by Dead_wall' 'Cyan'
Say 'Готово. В Cinema 4D: Extensions > SimRCL by Dead_wall' 'Cyan'
exit 0
