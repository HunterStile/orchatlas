# Install this checkout as a local editable CLI. Does not publish a package or release.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$sourceDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExecutable = (Get-Command python -ErrorAction Stop).Source
& $pythonExecutable -m pip install --user --editable $sourceDirectory
if ($LASTEXITCODE -ne 0) { throw 'Local editable installation failed.' }
$scriptDirectory = (& $pythonExecutable -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the Python user command directory.' }
$launcher = Join-Path $scriptDirectory 'orchatlas.exe'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'OrchAtlas launcher was not installed.' }
$userPathValue = [Environment]::GetEnvironmentVariable('Path', 'User')
$userEntries = @($userPathValue -split ';' | Where-Object { $_ })
if ($userEntries -notcontains $scriptDirectory) {
    [Environment]::SetEnvironmentVariable('Path', (($userEntries + $scriptDirectory) -join ';'), 'User')
}
if (($env:Path -split ';') -notcontains $scriptDirectory) { $env:Path = $env:Path + ';' + $scriptDirectory }
& $launcher --version
if ($LASTEXITCODE -ne 0) { throw 'Installed launcher did not start.' }
Write-Host 'Installed from this checkout. In a new PowerShell terminal, run: orchatlas'
Write-Host "Launcher: $launcher"
