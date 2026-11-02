<#
.SYNOPSIS
  Restore a ProcuraFlow backup made by deploy/backup.ps1 or deploy/backup.sh. REPLACES THE CURRENT DATABASE CONTENT.
.DESCRIPTION
  PowerShell equivalent of deploy/restore.sh. Without -Yes you must type the database name to confirm.
  The API is stopped during the restore and started again afterwards.
.EXAMPLE
  .\deploy\restore.ps1 -DatabaseDump .\deploy\backups\procuraflow-db-20260101T020000Z.dump
  .\deploy\restore.ps1 -DatabaseDump db.dump -UploadsArchive uploads.tar.gz -Yes
#>
param(
    [Parameter(Mandatory = $true)][string]$DatabaseDump,
    [string]$UploadsArchive,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $RootDir '.env'
$ComposeFile = Join-Path $ScriptDir 'docker-compose.yml'
$Compose = "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`""

if (-not (Test-Path $EnvFile)) { throw "$EnvFile not found" }
$DatabaseDump = (Resolve-Path $DatabaseDump).Path
if ((Get-Item $DatabaseDump).Length -eq 0) { throw "dump '$DatabaseDump' is empty" }
if ($UploadsArchive) {
    $UploadsArchive = (Resolve-Path $UploadsArchive).Path
    if ((Get-Item $UploadsArchive).Length -eq 0) { throw "uploads archive '$UploadsArchive' is empty" }
}

function Get-EnvValue([string]$Name, [string]$Default) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if ($null -eq $line) { return $Default }
    $value = ($line -split '=', 2)[1].Trim()
    if ($value -eq '') { return $Default }
    return $value
}

$DbUser = Get-EnvValue 'POSTGRES_USER' 'procuraflow'
$DbName = Get-EnvValue 'POSTGRES_DB' 'procuraflow'

Write-Host "About to REPLACE the contents of database '$DbName' with $DatabaseDump"
if ($UploadsArchive) { Write-Host "and REPLACE the uploaded files with $UploadsArchive" }
if (-not $Yes) {
    $answer = Read-Host "Type the database name ($DbName) to continue"
    if ($answer -ne $DbName) {
        Write-Host 'Aborted: nothing was changed.'
        exit 1
    }
}

function Invoke-Cmd([string]$Command) {
    # A temporary batch file avoids PowerShell 5.1 and cmd.exe fighting over nested quotes and redirection.
    $batch = Join-Path ([IO.Path]::GetTempPath()) ("procuraflow-" + [Guid]::NewGuid().ToString('N') + '.cmd')
    try {
        Set-Content -Path $batch -Value "@echo off`r`n$Command`r`nexit /b %ERRORLEVEL%" -Encoding Ascii
        & $env:ComSpec /c $batch | Out-Host
        return $LASTEXITCODE
    }
    finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $batch
    }
}

function Invoke-Checked([string]$Command) {
    $code = Invoke-Cmd $Command
    if ($code -ne 0) { throw "Command failed (exit $code): $Command" }
}

Write-Host 'Stopping the API ...'
Invoke-Checked "$Compose stop backend"

Write-Host 'Restoring the database ...'
# cmd.exe feeds the file to the container byte for byte; PowerShell's own pipeline would re-encode it as text.
Invoke-Checked "$Compose exec -T postgres pg_restore -U $DbUser -d $DbName --clean --if-exists --no-owner --exit-on-error < `"$DatabaseDump`""

if ($UploadsArchive) {
    Write-Host 'Restoring uploaded files ...'
    Invoke-Checked "$Compose run --rm --no-deps -T --entrypoint sh backend -c `"find /app/var/uploads -mindepth 1 -delete && tar -xzf - -C /app/var/uploads`" < `"$UploadsArchive`""
}

Write-Host 'Starting the API ...'
Invoke-Checked "$Compose start backend"
Write-Host 'Restore finished. Sign in and check the data. The API applies any newer migrations when it starts.'
