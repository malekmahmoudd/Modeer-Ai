<#
.SYNOPSIS
    Back up the Modeer database: dump, verify, encrypt, prune, and optionally copy off-host.

.DESCRIPTION
    A backup nobody has restored is a guess, so this verifies every archive with
    pg_restore --list before it counts as a backup. The dump contains the whole
    personal-memory store, so it is encrypted at rest with AES-256 whenever a
    passphrase is available and never written anywhere the repository tracks.

    Restore a verified archive with restore-check.ps1 before trusting it.

.PARAMETER Directory
    Where archives are written. Defaults to deploy/backups, which is gitignored.

.PARAMETER KeepDays
    Delete archives older than this. 0 disables pruning.

.PARAMETER OffHost
    A second location (mounted share, synced folder, rclone remote path) to copy
    the encrypted archive to. A backup on the same disk as the database is not
    a backup.

.PARAMETER PassphraseFile
    File holding the AES-256 passphrase. Defaults to $env:MODEER_BACKUP_PASSPHRASE_FILE.
    Without one the script warns and leaves the archive unencrypted.

.EXAMPLE
    ./backup.ps1 -KeepDays 30 -OffHost E:\offsite\modeer
#>
param(
    [string]$Directory = "$PSScriptRoot/backups",
    [int]$KeepDays = 30,
    [string]$OffHost = $env:MODEER_BACKUP_OFFHOST,
    [string]$PassphraseFile = $env:MODEER_BACKUP_PASSPHRASE_FILE
)

$ErrorActionPreference = 'Stop'
$compose = @('compose', '--project-directory', $PSScriptRoot, '-f', "$PSScriptRoot/compose.yml")

New-Item -ItemType Directory -Force -Path $Directory | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $Directory "modeer-$stamp.dump"

# Write the binary archive inside the container, then copy without shell redirection.
& docker @compose exec -T db pg_dump -U modeer -Fc -f /tmp/modeer-backup.dump modeer
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }

$dbContainer = (& docker @compose ps -q db).Trim()
if (-not $dbContainer) { throw 'Database container is not running' }

& docker cp "${dbContainer}:/tmp/modeer-backup.dump" $destination
if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed' }

# Verify the archive is readable as an archive, not merely non-empty.
& docker @compose exec -T db pg_restore --list /tmp/modeer-backup.dump | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Backup archive is invalid' }
& docker @compose exec -T db rm -f /tmp/modeer-backup.dump | Out-Null

$artifact = $destination

# --- encrypt at rest -------------------------------------------------------
if ($PassphraseFile -and (Test-Path $PassphraseFile)) {
    $encrypted = "$destination.enc"
    # openssl lives in the postgres image, so no host dependency is needed.
    & docker run --rm -i -v "${Directory}:/backup" postgres:16-alpine `
        sh -c "openssl enc -aes-256-cbc -pbkdf2 -iter 240000 -salt -pass stdin `
               -in /backup/$(Split-Path $destination -Leaf) `
               -out /backup/$(Split-Path $encrypted -Leaf)" `
        < $PassphraseFile
    if ($LASTEXITCODE -ne 0) { throw 'Backup encryption failed' }
    Remove-Item $destination -Force
    $artifact = $encrypted
    Write-Output "Encrypted: $artifact"
}
else {
    Write-Warning @'
Backup is NOT encrypted: no passphrase file.
It contains every stored personal memory. Set MODEER_BACKUP_PASSPHRASE_FILE
(or pass -PassphraseFile) before keeping backups anywhere but this host.
'@
}

# --- copy off-host ---------------------------------------------------------
if ($OffHost) {
    New-Item -ItemType Directory -Force -Path $OffHost | Out-Null
    Copy-Item $artifact -Destination $OffHost -Force
    Write-Output "Copied off-host: $OffHost"
}
else {
    Write-Warning 'No off-host copy: set -OffHost or MODEER_BACKUP_OFFHOST.'
}

# --- retention -------------------------------------------------------------
if ($KeepDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$KeepDays)
    $stale = Get-ChildItem -Path $Directory -Filter 'modeer-*.dump*' -File |
             Where-Object { $_.LastWriteTime -lt $cutoff }
    foreach ($file in $stale) {
        Remove-Item $file.FullName -Force
        Write-Output "Pruned: $($file.Name)"
    }
}

Write-Output "Backup saved: $artifact"
