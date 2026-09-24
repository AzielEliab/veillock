# Build the VeilLock Windows 11 user-mode virtual camera.
# Requires the Windows 11 SDK (build 22000+) and MSVC. No kernel driver.
# This script does not register the camera; veilcam-register.exe does that.
# Author: Aziel Eliab.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    Write-Error "cl.exe is not on PATH. Open a Visual Studio x64 developer prompt. Nothing was registered."
}

cl.exe /nologo /LD /EHsc /O2 /std:c++17 /DUNICODE /D_UNICODE /DWIN32_LEAN_AND_MEAN veilcam.cpp `
    /link /DEF:veilcam.def mfplat.lib mfuuid.lib ole32.lib advapi32.lib
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

cl.exe /nologo /EHsc /O2 /std:c++17 /DUNICODE /D_UNICODE /DWIN32_LEAN_AND_MEAN register.cpp `
    /link mfsensorgroup.lib mfplat.lib mfuuid.lib ole32.lib advapi32.lib
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Built veilcam.dll and veilcam-register.exe. Run veilcam-register.exe on Windows 11 build 22000 or newer to register the camera. This build step did not register it."
