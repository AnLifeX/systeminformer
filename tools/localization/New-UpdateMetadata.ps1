[CmdletBinding(DefaultParameterSetName = 'Base64Key')]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$SetupPath,

    [Parameter(Mandatory)]
    [string]$OutputPath,

    [Parameter(Mandatory)]
    [ValidatePattern('^\d+\.\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$Commit,

    [Parameter(Mandatory)]
    [ValidatePattern('^https://')]
    [string]$SetupUrl,

    [Parameter(Mandatory, ParameterSetName = 'Base64Key')]
    [string]$PrivateKeyBase64,

    [Parameter(Mandatory, ParameterSetName = 'KeyFile')]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$PrivateKeyPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedSetupPath = (Resolve-Path -LiteralPath $SetupPath).Path
$setupBytes = [System.IO.File]::ReadAllBytes($resolvedSetupPath)

if ($PSCmdlet.ParameterSetName -eq 'Base64Key') {
    try {
        $privateKeyPem = [System.Text.Encoding]::UTF8.GetString(
            [System.Convert]::FromBase64String($PrivateKeyBase64)
        )
    }
    catch {
        throw 'UPDATE_SIGNING_PRIVATE_KEY_B64 is not valid Base64-encoded UTF-8 PEM.'
    }
}
else {
    $privateKeyPem = [System.IO.File]::ReadAllText(
        (Resolve-Path -LiteralPath $PrivateKeyPath).Path,
        [System.Text.Encoding]::UTF8
    )
}

$signingKey = [System.Security.Cryptography.ECDsa]::Create()
try {
    $signingKey.ImportFromPem($privateKeyPem)

    if ($signingKey.KeySize -ne 256) {
        throw "The updater signing key must use ECDSA P-256; found $($signingKey.KeySize) bits."
    }

    $signatureFormat = [System.Security.Cryptography.DSASignatureFormat]::IeeeP1363FixedFieldConcatenation
    $signature = $signingKey.SignData(
        $setupBytes,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        $signatureFormat
    )

    if (-not $signingKey.VerifyData(
        $setupBytes,
        $signature,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        $signatureFormat
    )) {
        throw 'The generated updater signature did not pass verification.'
    }
}
finally {
    $signingKey.Dispose()
    $privateKeyPem = $null
}

$hash = [System.Security.Cryptography.SHA256]::HashData($setupBytes)
$updated = [DateTime]::UtcNow.Date.ToString(
    'yyyy-MM-ddTHH:mm:ss',
    [System.Globalization.CultureInfo]::InvariantCulture
)

$metadata = [ordered]@{
    version      = $Version
    updated      = $updated
    commit       = $Commit.ToLowerInvariant()
    setup_length = $setupBytes.LongLength
    setup_hash   = [System.Convert]::ToHexString($hash)
    setup_sig    = [System.Convert]::ToHexString($signature)
    setup_url    = $SetupUrl
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [System.IO.Path]::GetDirectoryName($outputFullPath)
if ($outputDirectory) {
    [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}

$json = $metadata | ConvertTo-Json
[System.IO.File]::WriteAllText(
    $outputFullPath,
    $json + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Created signed update metadata: $outputFullPath"
Write-Host "Version: $Version"
Write-Host "SHA-256: $($metadata.setup_hash)"
Write-Host "Signature bytes: $($signature.Length)"
