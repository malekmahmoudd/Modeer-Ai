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

.PARAMETER OpensslImage
    Image supplying openssl. Pinned, because the encryption of every backup
    depends on it. The postgres image does not ship openssl.

.EXAMPLE
    ./backup.ps1 -KeepDays 30 -OffHost E:\offsite\modeer
#>
param(
    [string]$Directory = "$PSScriptRoot/backups",
    [int]$KeepDays = 30,
    [string]$OffHost = $env:MODEER_BACKUP_OFFHOST,
    [string]$PassphraseFile = $env:MODEER_BACKUP_PASSPHRASE_FILE,
    [string]$OpensslImage = 'alpine/openssl:3.5.8'
)

$ErrorActionPreference = 'Stop'
$compose = @('compose', '--project-directory', $PSScriptRoot, '-f', "$PSScriptRoot/compose.yml")
# Windows PowerShell turns a native command's stderr into a terminating error
# under ErrorActionPreference='Stop', even on exit code 0 -- a single psql
# NOTICE would abort a backup that was working. Exit codes are checked instead.
$PSNativeCommandUseErrorActionPreference = $false

function Invoke-Native {
    param([Parameter(Mandatory)][scriptblock]$Command, [Parameter(Mandatory)][string]$OnFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { "$_" } | Out-Null }
    finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { throw $OnFailure }
}

New-Item -ItemType Directory -Force -Path $Directory | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $Directory "modeer-$stamp.dump"

# Write the binary archive inside the container, then copy without shell redirection.
Invoke-Native { & docker @compose exec -T db pg_dump -U modeer -Fc -f /tmp/modeer-backup.dump modeer } 'Database backup failed'

$dbContainer = (& docker @compose ps -q db).Trim()
if (-not $dbContainer) { throw 'Database container is not running' }

Invoke-Native { & docker cp "${dbContainer}:/tmp/modeer-backup.dump" $destination } 'Backup copy failed'

# Verify the archive is readable as an archive, not merely non-empty.
Invoke-Native { & docker @compose exec -T db pg_restore --list /tmp/modeer-backup.dump } 'Backup archive is invalid'
Invoke-Native { & docker @compose exec -T db rm -f /tmp/modeer-backup.dump } 'Could not clean up the in-container dump'

$artifact = $destination

# --- encrypt at rest -------------------------------------------------------
if ($PassphraseFile -and (Test-Path $PassphraseFile)) {
    $encrypted = "$destination.enc"
    $plainName = Split-Path $destination -Leaf
    $encName = Split-Path $encrypted -Leaf
    # openssl runs in a container so the host needs no crypto tooling. The
    # archive is plain `openssl enc`, so a human can decrypt it during a
    # real recovery with standard tools and none of this script.
    # PowerShell has no "<" redirection, so the passphrase is piped to stdin.
    # The passphrase file is mounted and read by openssl itself, never piped:
    # PowerShell appends a carriage return to piped stdin, which silently became
    # part of the passphrase and made archives decryptable only from PowerShell.
    # The image's entrypoint is openssl, so pass its arguments directly.
    $passDir = (Resolve-Path (Split-Path $PassphraseFile)).Path
    $passName = Split-Path $PassphraseFile -Leaf
    Invoke-Native {
        & docker run --rm -v "${Directory}:/backup" -v "${passDir}:/pass:ro" $OpensslImage `
            enc -aes-256-cbc -pbkdf2 -iter 240000 -salt -pass "file:/pass/$passName" `
            -in "/backup/$plainName" -out "/backup/$encName"
    } 'Backup encryption failed'

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
