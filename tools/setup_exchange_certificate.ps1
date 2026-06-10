$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OutDir = Join-Path $ProjectRoot "tools"
$CertPath = Join-Path $OutDir "exchange-cba-public.cer"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$cert = New-SelfSignedCertificate `
    -Subject "CN=M365 Account Analyzer Exchange CBA" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeySpec KeyExchange `
    -KeyLength 2048 `
    -KeyAlgorithm RSA `
    -HashAlgorithm SHA256 `
    -Provider "Microsoft Enhanced RSA and AES Cryptographic Provider" `
    -NotAfter (Get-Date).AddYears(2)

Export-Certificate -Cert $cert -FilePath $CertPath | Out-Null

Write-Host "Certificat cree dans Cert:\CurrentUser\My" -ForegroundColor Green
Write-Host "Thumbprint a mettre dans .env :" -ForegroundColor Yellow
Write-Host $cert.Thumbprint
Write-Host ""
Write-Host "Fichier public a televerser dans l'App Registration > Certificates & secrets > Certificates :" -ForegroundColor Yellow
Write-Host $CertPath
