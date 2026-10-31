<#
Cópia de segurança do SIGEST: base de dados MySQL + documentos privados.
Uso:  .\scripts\backup.ps1                       (pede a palavra-passe do MySQL)
      .\scripts\backup.ps1 -Utilizador garcia -Base sigest -Destino D:\copias
Guarde as cópias fora da máquina do servidor (disco externo ou outro computador).
#>
param(
    [string]$Utilizador = "garcia",
    [string]$Base = "sigest",
    [string]$Destino = "backups"
)

$data = Get-Date -Format "yyyyMMdd_HHmm"
New-Item -ItemType Directory -Force $Destino | Out-Null

$sql = Join-Path $Destino "sigest_$data.sql"
mysqldump --single-transaction --default-character-set=utf8mb4 --result-file="$sql" -u $Utilizador -p $Base
if ($LASTEXITCODE -ne 0) { Write-Error "Falha no mysqldump."; exit 1 }
Write-Output "OK  base de dados: $sql"

if (Test-Path "privado") {
    $zip = Join-Path $Destino "privado_$data.zip"
    Compress-Archive -Path "privado" -DestinationPath $zip
    Write-Output "OK  documentos:    $zip"
}