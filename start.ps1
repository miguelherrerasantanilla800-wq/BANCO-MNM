param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$envPath = Join-Path $PSScriptRoot ".env"
$examplePath = Join-Path $PSScriptRoot ".env.example"
$createdEnv = $false
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
    $createdEnv = $true
}

$lines = @([System.IO.File]::ReadAllLines($envPath))

function New-UrlSafeSecret {
    param([int]$ByteCount = 32, [switch]$KeepPadding)

    $bytes = New-Object byte[] $ByteCount
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    $secret = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
    if (-not $KeepPadding) {
        $secret = $secret.TrimEnd("=")
    }
    return $secret
}

$secretValues = [ordered]@{
    POSTGRES_PASSWORD = New-UrlSafeSecret
    JWT_SECRET = New-UrlSafeSecret -ByteCount 48
    AIRFLOW_POSTGRES_PASSWORD = New-UrlSafeSecret
    AIRFLOW_FERNET_KEY = New-UrlSafeSecret -KeepPadding
    AIRFLOW_WEBSERVER_SECRET_KEY = New-UrlSafeSecret -ByteCount 48
    AIRFLOW_ADMIN_USERNAME = "admin"
    AIRFLOW_ADMIN_PASSWORD = New-UrlSafeSecret
    GRAFANA_ADMIN_USER = "admin"
    GRAFANA_ADMIN_PASSWORD = New-UrlSafeSecret
}

$adminPasswordGenerated = $false
$grafanaPasswordGenerated = $false
foreach ($entry in $secretValues.GetEnumerator()) {
    $key = [regex]::Escape($entry.Key)
    $index = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$key=") {
            $index = $i
            break
        }
    }

    if ($index -ge 0) {
        $value = ($lines[$index] -split "=", 2)[1]
        if ($entry.Key -eq "POSTGRES_PASSWORD" -and -not $createdEnv -and $value) {
            continue
        }
        if ($value -and $value -notmatch "^(replace-with|change-this|generate-)") {
            continue
        }
        $lines[$index] = "$($entry.Key)=$($entry.Value)"
    }
    else {
        $lines += "$($entry.Key)=$($entry.Value)"
    }

    if ($entry.Key -eq "AIRFLOW_ADMIN_PASSWORD") {
        $adminPasswordGenerated = $true
    }
    if ($entry.Key -eq "GRAFANA_ADMIN_PASSWORD") {
        $grafanaPasswordGenerated = $true
    }
}

$encoding = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllLines($envPath, [string[]]$lines, $encoding)

$images = @{
    APP_IMAGE = "bancomnm/app:local"
    HADOOP_IMAGE = "bancomnm/hadoop:local"
    AIRFLOW_IMAGE = "bancomnm/airflow:local"
    MONITORING_IMAGE = "bancomnm/monitoring:local"
}
foreach ($line in $lines) {
    if ($line -match "^(APP_IMAGE|HADOOP_IMAGE|AIRFLOW_IMAGE|MONITORING_IMAGE)=(.*)$") {
        $images[$matches[1]] = $matches[2]
    }
}

$needsBuild = $Build
if (-not $needsBuild) {
    $localImages = @(& docker image ls --format "{{.Repository}}:{{.Tag}}")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect local Docker images"
    }
    foreach ($image in $images.Values) {
        if ($image -notin $localImages) {
            $needsBuild = $true
            break
        }
    }
}

$composeArgs = @("compose", "up", "-d")
if ($needsBuild) {
    $composeArgs += "--build"
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

docker compose ps
if ($adminPasswordGenerated) {
    $adminLine = $lines | Where-Object { $_ -match "^AIRFLOW_ADMIN_PASSWORD=" } | Select-Object -Last 1
    $adminPassword = ($adminLine -split "=", 2)[1]
    Write-Host "Airflow login: admin / $adminPassword"
}
if ($grafanaPasswordGenerated) {
    $grafanaUserLine = $lines | Where-Object { $_ -match "^GRAFANA_ADMIN_USER=" } | Select-Object -Last 1
    $grafanaPasswordLine = $lines | Where-Object { $_ -match "^GRAFANA_ADMIN_PASSWORD=" } | Select-Object -Last 1
    $grafanaUser = ($grafanaUserLine -split "=", 2)[1]
    $grafanaPassword = ($grafanaPasswordLine -split "=", 2)[1]
    Write-Host "Grafana login: $grafanaUser / $grafanaPassword"
}
