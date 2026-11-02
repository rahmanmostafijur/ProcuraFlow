<#
.SYNOPSIS
  Back up the ProcuraFlow database (pg_dump custom format) and the uploaded files, then prune old backups.
.DESCRIPTION
  PowerShell equivalent of deploy/backup.sh. Reads POSTGRES_USER, POSTGRES_DB and BACKUP_RETENTION_DAYS from the
  repository's .env (defaults: procuraflow, procuraflow, 14). The stack must be running.
  Binary output goes through cmd.exe redirection because PowerShell 5.1 would re-encode it as text.
.EXAMPLE
  .\deploy\backup.ps1
  .\deploy\backup.ps1 -BackupDir D:\backups\procuraflow
#>
param(
    [string]$BackupDir
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $RootDir '.env'
$ComposeFile = Join-Path $ScriptDir 'docker-compose.yml'

if (-not (Test-Path $EnvFile)) { throw "$EnvFile not found" }

function Get-EnvValue([string]$Name, [string]$Default) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if ($null -eq $line) { return $Default }
    $value = ($line -split '=', 2)[1].Trim()
    if ($value -eq '') { return $Default }
    return $value
}

$DbUser = Get-EnvValue 'POSTGRES_USER' 'procuraflow'
$DbName = Get-EnvValue 'POSTGRES_DB' 'procuraflow'
$RetentionText = Get-EnvValue 'BACKUP_RETENTION_DAYS' '14'
if ($RetentionText -notmatch '^\d+$') { throw "BACKUP_RETENTION_DAYS must be a whole number, got '$RetentionText'" }
$RetentionDays = [int]$RetentionText

if (-not $BackupDir) { $BackupDir = Join-Path $ScriptDir 'backups' }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$DbFile = Join-Path $BackupDir "procuraflow-db-$Stamp.dump"
$FilesArchive = Join-Path $BackupDir "procuraflow-uploads-$Stamp.tar.gz"
$Compose = "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`""

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

function Invoke-RawToFile([string]$Command, [string]$Target) {
    $partial = "$Target.partial"
    $code = Invoke-Cmd "$Command > `"$partial`""
    if ($code -ne 0 -or -not (Test-Path $partial) -or (Get-Item $partial).Length -eq 0) {
        Remove-Item -Force -ErrorAction SilentlyContinue $partial
        throw "Command failed or produced no output: $Command"
    }
    Move-Item -Force $partial $Target
}

Write-Host "Dumping database $DbName ..."
Invoke-RawToFile "$Compose exec -T postgres pg_dump -U $DbUser -d $DbName --format=custom --no-owner" $DbFile

Write-Host 'Archiving uploaded files ...'
Invoke-RawToFile "$Compose exec -T backend tar -czf - -C /app/var/uploads ." $FilesArchive

Write-Host "Pruning backups older than $RetentionDays days ..."
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -File |
    Where-Object { $_.Name -match '^procuraflow-(db-.*\.dump|uploads-.*\.tar\.gz)$' -and $_.LastWriteTime -lt $cutoff } |
    ForEach-Object { Write-Host "  deleting $($_.FullName)"; Remove-Item -Force $_.FullName }

Write-Host 'Done:'
Write-Host "  $DbFile"
Write-Host "  $FilesArchive"
Write-Host 'Copy these off the server; a backup on the same disk does not survive losing the disk.'
