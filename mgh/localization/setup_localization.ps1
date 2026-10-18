param([string]$Python = 'python')

$ErrorActionPreference = 'Stop'
$workspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$environment = Join-Path $workspace 'work/mgh_localization_env'
$runtime = Join-Path $environment 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    & $Python -m venv $environment
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& $runtime -m pip install 'torch==2.14.1+cpu' 'torchvision==0.29.1+cpu' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
& $runtime -m pip install 'opencv-python-headless==5.0.0.93' 'numpy==2.5.2' 'Pillow==12.3.0' 'kornia==0.8.3' 'kornia-rs==0.2.0'
if ($LASTEXITCODE -ne 0) { throw 'Feature runtime installation failed.' }
$vendorRoot = Join-Path $workspace 'work/LightGlue'
if (-not (Test-Path -LiteralPath $vendorRoot)) {
    $sourceArchive = Join-Path $PSScriptRoot 'vendor/lightglue-disk-subset-eb42fee2d714.zip'
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $vendorRoot
}
& $runtime (Join-Path $PSScriptRoot 'mgh_localizer.py') --help
if ($LASTEXITCODE -ne 0) { throw 'Localizer import check failed.' }
