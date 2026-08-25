param(
    [string]$ProjectRoot = "C:\Users\25fel\Documents\appContableGato"
)

$Backend = Join-Path $ProjectRoot "backend"
$Database = Join-Path $Backend "gato_contable.db"
$BackupDir = Join-Path $ProjectRoot "backups"

if (!(Test-Path $Database)) {
    throw "No se encontró la base de datos: $Database"
}

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force |
Out-Null

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

$Destination = Join-Path `
    $BackupDir `
    "la-patrona-$Timestamp.db"

Copy-Item `
    $Database `
    $Destination `
    -Force

Write-Host ""
Write-Host "Backup creado:" -ForegroundColor Green
Write-Host $Destination
