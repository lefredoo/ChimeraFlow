<#
.SYNOPSIS
Production smoke test: checks the deployed API end to end with the public demo account.

.DESCRIPTION
Required environment variables:
  SMOKE_EMAIL     demo account email (public by design, still never hardcoded here)
  SMOKE_PASSWORD  demo account password
Works on PowerShell 7 and Windows PowerShell 5.1. Exit code 0 when every check
passes, 1 when a check fails, 2 when the environment is incomplete.
The access token is never printed.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ApiUrl = 'https://chimeraflow-api.linguasolution.com'
$WebOrigin = 'https://chimeraflow.linguasolution.com'
$ExpectedPredefinedRules = 5

$missing = @()
if ([string]::IsNullOrEmpty($env:SMOKE_EMAIL)) { $missing += 'SMOKE_EMAIL' }
if ([string]::IsNullOrEmpty($env:SMOKE_PASSWORD)) { $missing += 'SMOKE_PASSWORD' }
if ($missing.Count -gt 0) {
    [Console]::Error.WriteLine("Missing required environment variable(s): $($missing -join ' ') (demo account credentials)")
    exit 2
}

# Windows PowerShell 5.1 does not enable TLS 1.2 by default
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.Net.Http

$client = New-Object System.Net.Http.HttpClient
$client.Timeout = [TimeSpan]::FromSeconds(30)

$script:Passed = 0
$script:Failures = New-Object System.Collections.Generic.List[string]

function Add-Pass([string]$Message) {
    $script:Passed++
    Write-Host "[ OK ] $Message"
}

function Add-Failure([string]$Message) {
    $script:Failures.Add($Message)
    Write-Host "[FAIL] $Message"
}

# Sends a request and returns Status, Body (parsed JSON or $null) and Headers; never throws on HTTP errors.
function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token,
        [string]$JsonBody,
        [hashtable]$ExtraHeaders
    )
    $request = New-Object System.Net.Http.HttpRequestMessage ([System.Net.Http.HttpMethod]::new($Method), "$ApiUrl$Path")
    if ($Token) {
        [void]$request.Headers.TryAddWithoutValidation('Authorization', "Bearer $Token")
    }
    if ($ExtraHeaders) {
        foreach ($name in $ExtraHeaders.Keys) {
            [void]$request.Headers.TryAddWithoutValidation($name, [string]$ExtraHeaders[$name])
        }
    }
    if ($JsonBody) {
        $request.Content = New-Object System.Net.Http.StringContent ($JsonBody, [Text.Encoding]::UTF8, 'application/json')
    }
    try {
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
    } catch {
        return [pscustomobject]@{ Status = 0; Body = $null; Headers = @{} }
    }
    $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    $parsed = $null
    if ($text) {
        try { $parsed = $text | ConvertFrom-Json } catch { $parsed = $null }
    }
    $headers = @{}
    foreach ($header in $response.Headers) { $headers[$header.Key.ToLowerInvariant()] = ($header.Value -join ',') }
    return [pscustomobject]@{ Status = [int]$response.StatusCode; Body = $parsed; Headers = $headers }
}

function Test-Status([string]$Label, $Response, [int]$Expected) {
    if ($Response.Status -eq $Expected) { Add-Pass "$Label (HTTP $($Response.Status))" }
    else { Add-Failure "${Label}: expected HTTP $Expected, got $($Response.Status)" }
}

function Write-Summary {
    Write-Host ''
    Write-Host "Smoke test: $($script:Passed) passed, $($script:Failures.Count) failed"
    foreach ($failure in $script:Failures) { Write-Host " - $failure" }
}

# 1. Health
$r = Invoke-Api -Method GET -Path '/health'
Test-Status 'GET /health' $r 200
if ($r.Body -and $r.Body.status -eq 'ok') { Add-Pass 'health status is ok' } else { Add-Failure 'health status is not ok' }

# 2. Interactive docs must not be published
$r = Invoke-Api -Method GET -Path '/docs'
Test-Status 'GET /docs is not exposed' $r 404

# 3. Protected routes refuse anonymous requests
$r = Invoke-Api -Method GET -Path '/api/v1/sources'
Test-Status 'GET /api/v1/sources without token' $r 401

# 4. Login
$loginBody = @{ email = $env:SMOKE_EMAIL; password = $env:SMOKE_PASSWORD } | ConvertTo-Json -Compress
$r = Invoke-Api -Method POST -Path '/api/v1/auth/login' -JsonBody $loginBody
Test-Status 'POST /api/v1/auth/login' $r 200
$token = $null
if ($r.Body -and $r.Body.PSObject.Properties['access_token']) { $token = [string]$r.Body.access_token }
if (-not $token) {
    Add-Failure 'login returned no access token'
    Write-Summary
    $client.Dispose()
    exit 1
}

# 5. Authenticated identity
$r = Invoke-Api -Method GET -Path '/api/v1/auth/me' -Token $token
Test-Status 'GET /api/v1/auth/me' $r 200
if ($r.Body -and $r.Body.email -eq $env:SMOKE_EMAIL) { Add-Pass '/auth/me returns the demo account' } else { Add-Failure '/auth/me does not return the demo account' }

# 6. Sources: all four connectors healthy
$r = Invoke-Api -Method GET -Path '/api/v1/sources' -Token $token
Test-Status 'GET /api/v1/sources' $r 200
$sources = @()
if ($r.Body -and $r.Body.PSObject.Properties['sources']) { $sources = @($r.Body.sources) }
$notOk = @($sources | Where-Object { $_.status -ne 'ok' }).Count
if ($sources.Count -eq 4 -and $notOk -eq 0) { Add-Pass '4 sources, all ok' }
else { Add-Failure "sources: expected 4 all ok, got $($sources.Count) with $notOk not ok" }

# 7. Predefined rules
$r = Invoke-Api -Method GET -Path '/api/v1/rules/predefined' -Token $token
Test-Status 'GET /api/v1/rules/predefined' $r 200
$ruleCount = @($r.Body).Count
if ($ruleCount -eq $ExpectedPredefinedRules) { Add-Pass "$ruleCount predefined rules" }
else { Add-Failure "predefined rules: expected $ExpectedPredefinedRules, got $ruleCount" }

# 8. Correlation engine run
$r = Invoke-Api -Method POST -Path '/api/v1/correlations/execute' -Token $token
Test-Status 'POST /api/v1/correlations/execute' $r 200
if ($r.Body -and $r.Body.status -eq 'success' -and $r.Body.rules_failed -eq 0) {
    Add-Pass "execution success: $($r.Body.rules_executed) rules executed, 0 failed, $($r.Body.correlations_found) correlations"
} else {
    $runStatus = if ($r.Body) { $r.Body.status } else { 'none' }
    Add-Failure "execution: status=$runStatus, rules_failed=$(if ($r.Body) { $r.Body.rules_failed } else { '?' })"
}

# 9. Correlations listing
$r = Invoke-Api -Method GET -Path '/api/v1/correlations' -Token $token
Test-Status 'GET /api/v1/correlations' $r 200
if ($r.Status -eq 200) { Add-Pass "$(@($r.Body).Count) correlations listed" }

# 10. CORS: the frontend origin is allowed, another origin is not
$r = Invoke-Api -Method OPTIONS -Path '/api/v1/sources' -ExtraHeaders @{
    'Origin' = $WebOrigin
    'Access-Control-Request-Method' = 'GET'
    'Access-Control-Request-Headers' = 'authorization'
}
$allowed = $r.Headers['access-control-allow-origin']
if ($r.Status -eq 200 -and $allowed -eq $WebOrigin) { Add-Pass "CORS preflight allows $WebOrigin" }
else { Add-Failure "CORS preflight for ${WebOrigin}: HTTP $($r.Status), allow-origin='$allowed'" }
$r = Invoke-Api -Method OPTIONS -Path '/api/v1/sources' -ExtraHeaders @{
    'Origin' = 'https://evil.example'
    'Access-Control-Request-Method' = 'GET'
}
$foreign = $r.Headers['access-control-allow-origin']
if (-not $foreign) { Add-Pass 'CORS preflight refuses a foreign origin' } else { Add-Failure "CORS allows a foreign origin ('$foreign')" }

$client.Dispose()
Write-Summary
if ($script:Failures.Count -gt 0) { exit 1 }
