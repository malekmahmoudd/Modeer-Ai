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
    [string]$PassphraseFile = $env:MODEER_BACKUP_PASSPHRASE_FILE,
    [string]$OpensslImage = 'alpine/openssl:3.5.8'
)

$ErrorActionPreference = 'Stop'
$compose = @('compose', '--project-directory', $PSScriptRoot, '-f', "$PSScriptRoot/compose.yml")
$scratch = "modeer_restore_check"
# psql writes NOTICEs to stderr, and Windows PowerShell turns a native command's
# stderr into a terminating ErrorRecord under ErrorActionPreference='Stop' even
# when the command exited 0. Every native call below is checked via
# $LASTEXITCODE instead, which is the thing that actually reports failure.
$PSNativeCommandUseErrorActionPreference = $false

function Invoke-Native {
    param([Parameter(Mandatory)][scriptblock]$Command, [Parameter(Mandatory)][string]$OnFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { "$_" } | Out-Null }
    finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { throw $OnFailure }
}

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
    $archiveDir = Split-Path $Archive
    $archiveName = Split-Path $Archive -Leaf
    $outDir = [System.IO.Path]::GetTempPath()
    $outName = Split-Path $temporary -Leaf
    # PowerShell has no "<" redirection, so the passphrase is piped to stdin.
    # Mounted, not piped -- see the note in backup.ps1.
    $passDir = (Resolve-Path (Split-Path $PassphraseFile)).Path
    $passName = Split-Path $PassphraseFile -Leaf
    Invoke-Native {
        & docker run --rm -v "${archiveDir}:/backup" -v "${outDir}:/out" -v "${passDir}:/pass:ro" $OpensslImage `
            enc -d -aes-256-cbc -pbkdf2 -iter 240000 -pass "file:/pass/$passName" `
            -in "/backup/$archiveName" -out "/out/$outName"
    } 'Decryption failed'

    $plain = $temporary
}

try {
    Invoke-Native { & docker cp $plain "${dbContainer}:/tmp/restore-check.dump" } 'Copy into container failed'
    Invoke-Native { & docker @compose exec -T db psql -U modeer -d postgres -c "DROP DATABASE IF EXISTS $scratch" } 'Could not drop the scratch database'
    Invoke-Native { & docker @compose exec -T db psql -U modeer -d postgres -c "CREATE DATABASE $scratch" } 'Could not create the scratch database'
    Invoke-Native { & docker @compose exec -T db pg_restore -U modeer -d $scratch --no-owner /tmp/restore-check.dump } 'Restore failed'

    $query = @'
SELECT 'users=' || (SELECT count(*) FROM users)
    || ' shared_memories=' || (SELECT count(*) FROM shared_memories)
    || ' agent_memories=' || (SELECT count(*) FROM agent_memories)
    || ' messages=' || (SELECT count(*) FROM messages)
'@
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $counts = (& docker @compose exec -T db psql -U modeer -d $scratch -tAc $query) -join '' }
    finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { throw 'Restored database is not queryable' }
    $counts = $counts.Trim()
    Write-Output "Restored rows: $counts"
    if ($counts -match 'users=0\b') { throw 'Restored database has no users — archive is not usable' }
    Write-Output 'RESTORE CHECK PASSED'
}
finally {
    # Cleanup must never mask the real failure, so these ignore their own errors.
    $ErrorActionPreference = 'Continue'
    & docker @compose exec -T db psql -U modeer -d postgres -c "DROP DATABASE IF EXISTS $scratch" 2>&1 | Out-Null
    & docker @compose exec -T db rm -f /tmp/restore-check.dump 2>&1 | Out-Null
    if ($temporary -and (Test-Path $temporary)) { Remove-Item $temporary -Force }
}
