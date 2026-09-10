<#
.SYNOPSIS
    Restore a backup into a scratch database and prove it holds real rows.

.DESCRIPTION
    Restores into a throwaway database beside the live one, counts the rows that
    matter, and drops it again. The live database is never touched, so this is
    safe to run on a schedule — which is the point: an unrestored backup is a
    guess, and this is the only thing that turns it into a fact.

.PARAMETER Archive
    Path to a .dump (or .dump.enc) produced by backup.ps1. Defaults to the newest.

.PARAMETER PassphraseFile
    Required for a .enc archive. Defaults to $env:MODEER_BACKUP_PASSPHRASE_FILE.

.EXAMPLE
    ./restore-check.ps1
#>
param(
    [string]$Archive,
    [string]$Directory = "$PSScriptRoot/backups",
    [string]$PassphraseFile = $env:MODEER_BACKUP_PASSPHRASE_FILE
)

$ErrorActionPreference = 'Stop'
$compose = @('compose', '--project-directory', $PSScriptRoot, '-f', "$PSScriptRoot/compose.yml")
$scratch = "modeer_restore_check"

if (-not $Archive) {
    $newest = Get-ChildItem -Path $Directory -Filter 'modeer-*.dump*' -File |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $newest) { throw "No archives in $Directory" }
    $Archive = $newest.FullName
}
if (-not (Test-Path $Archive)) { throw "No such archive: $Archive" }
Write-Output "Checking: $Archive"

$dbContainer = (& docker @compose ps -q db).Trim()
if (-not $dbContainer) { throw 'Database container is not running' }

# Decrypt to a temporary plaintext copy that is always removed.
$plain = $Archive
$temporary = $null
if ($Archive.EndsWith('.enc')) {
    if (-not ($PassphraseFile -and (Test-Path $PassphraseFile))) {
        throw 'Encrypted archive needs -PassphraseFile'
    }
    $temporary = Join-Path ([System.IO.Path]::GetTempPath()) "modeer-restore-$PID.dump"
    & docker run --rm -i -v "$(Split-Path $Archive):/backup" -v "$([System.IO.Path]::GetTempPath()):/out" `
        postgres:16-alpine `
        sh -c "openssl enc -d -aes-256-cbc -pbkdf2 -iter 240000 -pass stdin `
               -in /backup/$(Split-Path $Archive -Leaf) -out /out/$(Split-Path $temporary -Leaf)" `
        < $PassphraseFile
    if ($LASTEXITCODE -ne 0) { throw 'Decryption failed' }
    $plain = $temporary
}

try {
    & docker cp $plain "${dbContainer}:/tmp/restore-check.dump"
    if ($LASTEXITCODE -ne 0) { throw 'Copy into container failed' }

    & docker @compose exec -T db psql -U modeer -d postgres -c "DROP DATABASE IF EXISTS $scratch" | Out-Null
    & docker @compose exec -T db psql -U modeer -d postgres -c "CREATE DATABASE $scratch" | Out-Null
    & docker @compose exec -T db pg_restore -U modeer -d $scratch --no-owner /tmp/restore-check.dump
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed' }

    $query = @'
SELECT 'users=' || (SELECT count(*) FROM users)
    || ' shared_memories=' || (SELECT count(*) FROM shared_memories)
    || ' agent_memories=' || (SELECT count(*) FROM agent_memories)
    || ' messages=' || (SELECT count(*) FROM messages)
'@
    $counts = (& docker @compose exec -T db psql -U modeer -d $scratch -tAc $query).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Restored database is not queryable' }
    Write-Output "Restored rows: $counts"
    if ($counts -match 'users=0\b') { throw 'Restored database has no users — archive is not usable' }
    Write-Output 'RESTORE CHECK PASSED'
}
finally {
    & docker @compose exec -T db psql -U modeer -d postgres -c "DROP DATABASE IF EXISTS $scratch" 2>&1 | Out-Null
    & docker @compose exec -T db rm -f /tmp/restore-check.dump 2>&1 | Out-Null
    if ($temporary -and (Test-Path $temporary)) { Remove-Item $temporary -Force }
}
