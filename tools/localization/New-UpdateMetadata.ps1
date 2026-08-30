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

    [ValidatePattern('^$|^[0-9a-fA-F]{40}$')]
    [string]$PreviousCommit = '',

    [Parameter(Mandatory)]
    [ValidatePattern('^https://')]
    [string]$SetupUrl,

    [ValidatePattern('^https://')]
    [string]$RepositoryUrl = 'https://github.com/AnLifeX/systeminformer',

    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$RepositoryRoot = (Join-Path (Join-Path $PSScriptRoot '..') '..'),

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

$repositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$commit = $Commit.ToLowerInvariant()
$previousCommit = $PreviousCommit.ToLowerInvariant()

& git -C $repositoryRoot cat-file -e "$commit^{commit}"
if ($LASTEXITCODE -ne 0) {
    throw "Release commit $commit does not exist in $repositoryRoot."
}

if ($previousCommit) {
    if ($previousCommit -eq $commit) {
        throw 'The previous release commit and current release commit must be different.'
    }

    & git -C $repositoryRoot cat-file -e "$previousCommit^{commit}"
    if ($LASTEXITCODE -ne 0) {
        throw "Previous release commit $previousCommit does not exist in $repositoryRoot."
    }

    & git -C $repositoryRoot merge-base --is-ancestor $previousCommit $commit
    if ($LASTEXITCODE -ne 0) {
        throw "Previous release commit $previousCommit is not an ancestor of $commit."
    }

    $changelogRevision = "$previousCommit..$commit"
}
else {
    # There is no earlier localized release boundary. Keep the first release finite
    # and anchored to its exact release commit rather than importing upstream history.
    $changelogRevision = $commit
}

$logLines = @(
    if ($previousCommit) {
        & git -C $repositoryRoot log '--format=%H%x09%aI%x09%an%x09%s' $changelogRevision
    }
    else {
        & git -C $repositoryRoot log -n 1 '--format=%H%x09%aI%x09%an%x09%s' $changelogRevision
    }
)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the Git changelog for revision $changelogRevision."
}

$changelog = @(
    foreach ($line in $logLines) {
        $parts = $line -split "`t", 4
        if ($parts.Count -ne 4 -or $parts[0] -notmatch '^[0-9a-fA-F]{40}$') {
            throw "Unexpected Git changelog record: $line"
        }

        $sha = $parts[0].ToLowerInvariant()
        $authorDate = [DateTimeOffset]::Parse(
            $parts[1],
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        ).UtcDateTime.ToString(
            'yyyy-MM-ddTHH:mm:ssZ',
            [System.Globalization.CultureInfo]::InvariantCulture
        )
        [ordered]@{
            sha      = $sha
            html_url = "$RepositoryUrl/commit/$sha"
            commit   = [ordered]@{
                message = $parts[3]
                author  = [ordered]@{
                    name = $parts[2]
                    date = $authorDate
                }
            }
        }
    }
)

if ($changelog.Count -eq 0 -or $changelog[0].sha -ne $commit) {
    throw "The changelog does not start at release commit $commit."
}

$metadata = [ordered]@{
    version      = $Version
    updated      = $updated
    commit       = $commit
    previous_commit = $previousCommit
    setup_length = $setupBytes.LongLength
    setup_hash   = [System.Convert]::ToHexString($hash)
    setup_sig    = [System.Convert]::ToHexString($signature)
    setup_url    = $SetupUrl
    changelog    = $changelog
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [System.IO.Path]::GetDirectoryName($outputFullPath)
if ($outputDirectory) {
    [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}

$json = $metadata | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText(
    $outputFullPath,
    $json + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Created signed update metadata: $outputFullPath"
Write-Host "Version: $Version"
Write-Host "SHA-256: $($metadata.setup_hash)"
Write-Host "Signature bytes: $($signature.Length)"
