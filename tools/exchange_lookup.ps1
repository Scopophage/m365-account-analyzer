param(
    [Parameter(Mandatory = $true)]
    [string]$InputJsonPath
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-PropValue {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

function ConvertTo-StringArray {
    param($Value)
    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { $_.ToString() })
}

function Convert-AccessRights {
    param($Value)
    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { $_.ToString() })
}

function Disconnect-Safely {
    try { Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue | Out-Null } catch {}
}

try {
    $payload = Get-Content -Path $InputJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

    Import-Module ExchangeOnlineManagement -ErrorAction Stop

    $connectParams = @{
        ShowBanner = $false
        ErrorAction = "Stop"
    }

    if ($payload.authMode -eq "app_certificate") {
        if (-not $payload.organization -or -not $payload.appId -or -not $payload.certificateThumbprint) {
            throw "Auth Exchange app_certificate incomplete : Organization, AppId et CertificateThumbprint sont requis."
        }
        $connectParams.Organization = [string]$payload.organization
        $connectParams.AppId = [string]$payload.appId
        $connectParams.CertificateThumbprint = [string]$payload.certificateThumbprint
        Connect-ExchangeOnline @connectParams | Out-Null
    }
    elseif ($payload.authMode -eq "interactive") {
        if (-not $payload.adminUpn) {
            throw "Auth Exchange interactive incomplete : EXCHANGE_ADMIN_UPN est requis."
        }
        $connectParams.UserPrincipalName = [string]$payload.adminUpn
        Connect-ExchangeOnline @connectParams | Out-Null
    }
    else {
        throw "EXCHANGE_AUTH_MODE invalide. Valeurs supportees : app_certificate ou interactive."
    }

    if ($payload.mode -eq "diagnostic") {
        $sample = Get-EXOMailbox -ResultSize 1 -ErrorAction Stop | Select-Object -First 1
        $response = [ordered]@{
            enabled = $true
            configured = $true
            available = $true
            ok = $true
            mode = "diagnostic"
            detail = "Connexion Exchange Online OK. Get-EXOMailbox fonctionne."
            sampleDisplayName = if ($sample) { $sample.DisplayName } else { $null }
            samplePrimarySmtpAddress = if ($sample) { $sample.PrimarySmtpAddress.ToString() } else { $null }
        }
        $response | ConvertTo-Json -Depth 8 -Compress
        Disconnect-Safely
        exit 0
    }

    $identifiers = @($payload.identifiers | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
    $tried = @()
    $mailbox = $null
    $matchedIdentifier = $null

    foreach ($id in $identifiers) {
        $tried += $id
        try {
            $mailbox = Get-EXOMailbox -Identity $id -Properties EmailAddresses,HiddenFromAddressListsEnabled,GrantSendOnBehalfTo -ErrorAction Stop
            $matchedIdentifier = $id
            break
        }
        catch {}
    }

    if ($null -eq $mailbox) {
        $recipient = $null
        $recipientMatchedIdentifier = $null
        foreach ($id in $identifiers) {
            try {
                $recipient = Get-EXORecipient -Identity $id -Properties EmailAddresses,HiddenFromAddressListsEnabled -ErrorAction Stop
                $recipientMatchedIdentifier = $id
                break
            }
            catch {}
        }

        if ($null -ne $recipient) {
            $rtype = (Get-PropValue $recipient "RecipientTypeDetails")
            $response = [ordered]@{
                enabled = $true
                configured = $true
                available = $true
                found = $true
                recipientFound = $true
                hasMailbox = $false
                matchedIdentifier = $recipientMatchedIdentifier
                displayName = $recipient.DisplayName
                primarySmtpAddress = if ($recipient.PrimarySmtpAddress) { $recipient.PrimarySmtpAddress.ToString() } else { $null }
                recipientTypeDetails = if ($rtype) { $rtype.ToString() } else { $null }
                hiddenFromAddressLists = [bool](Get-PropValue $recipient "HiddenFromAddressListsEnabled")
                aliases = ConvertTo-StringArray (Get-PropValue $recipient "EmailAddresses")
                source = "Exchange Online PowerShell Get-EXORecipient"
                tried = $tried
            }
            $response | ConvertTo-Json -Depth 8 -Compress
            Disconnect-Safely
            exit 0
        }

        $response = [ordered]@{
            enabled = $true
            configured = $true
            available = $true
            found = $false
            recipientFound = $false
            hasMailbox = $false
            matchedIdentifier = $null
            source = "Exchange Online PowerShell"
            tried = $tried
            error = "Aucune boite ou objet destinataire Exchange trouve avec les identifiants fournis."
        }
        $response | ConvertTo-Json -Depth 8 -Compress
        Disconnect-Safely
        exit 0
    }

    $stats = $null
    try { $stats = Get-EXOMailboxStatistics -Identity $mailbox.PrimarySmtpAddress -ErrorAction Stop } catch {}

    $fullAccess = @()
    $sendAs = @()
    if ([bool]$payload.includePermissions) {
        try {
            $fullAccess = @(Get-MailboxPermission -Identity $mailbox.PrimarySmtpAddress -ErrorAction Stop |
                Where-Object { $_.User -notlike "NT AUTHORITY\SELF" -and $_.IsInherited -eq $false -and $_.Deny -eq $false } |
                ForEach-Object {
                    [ordered]@{
                        user = $_.User.ToString()
                        accessRights = Convert-AccessRights $_.AccessRights
                    }
                })
        }
        catch {}

        try {
            $sendAs = @(Get-RecipientPermission -Identity $mailbox.PrimarySmtpAddress -ErrorAction Stop |
                Where-Object { $_.Trustee -notlike "NT AUTHORITY\SELF" -and $_.IsInherited -eq $false } |
                ForEach-Object {
                    [ordered]@{
                        trustee = $_.Trustee.ToString()
                        accessRights = Convert-AccessRights $_.AccessRights
                    }
                })
        }
        catch {}
    }

    $sendOnBehalf = ConvertTo-StringArray (Get-PropValue $mailbox "GrantSendOnBehalfTo")
    $recipientType = (Get-PropValue $mailbox "RecipientTypeDetails")
    $recipientTypeText = if ($recipientType) { $recipientType.ToString() } else { $null }
    $lastLogonTime = Get-PropValue $stats "LastLogonTime"
    $lastUserActionTime = Get-PropValue $stats "LastUserActionTime"
    $lastInteractionTime = Get-PropValue $stats "LastInteractionTime"

    $response = [ordered]@{
        enabled = $true
        configured = $true
        available = $true
        found = $true
        recipientFound = $true
        hasMailbox = $true
        matchedIdentifier = $matchedIdentifier
        displayName = $mailbox.DisplayName
        userPrincipalName = $mailbox.UserPrincipalName
        primarySmtpAddress = if ($mailbox.PrimarySmtpAddress) { $mailbox.PrimarySmtpAddress.ToString() } else { $null }
        recipientTypeDetails = $recipientTypeText
        isSharedMailbox = ($recipientTypeText -eq "SharedMailbox")
        isRoomMailbox = ($recipientTypeText -eq "RoomMailbox")
        isEquipmentMailbox = ($recipientTypeText -eq "EquipmentMailbox")
        hiddenFromAddressLists = [bool](Get-PropValue $mailbox "HiddenFromAddressListsEnabled")
        whenMailboxCreated = Get-PropValue $mailbox "WhenMailboxCreated"
        exchangeGuid = if ($mailbox.ExchangeGuid) { $mailbox.ExchangeGuid.ToString() } else { $null }
        externalDirectoryObjectId = Get-PropValue $mailbox "ExternalDirectoryObjectId"
        aliases = ConvertTo-StringArray (Get-PropValue $mailbox "EmailAddresses")
        itemCount = if ($stats) { Get-PropValue $stats "ItemCount" } else { $null }
        totalItemSize = if ($stats -and (Get-PropValue $stats "TotalItemSize")) { (Get-PropValue $stats "TotalItemSize").ToString() } else { $null }
        lastLogonTime = $lastLogonTime
        lastUserActionTime = $lastUserActionTime
        lastInteractionTime = $lastInteractionTime
        fullAccess = $fullAccess
        sendAs = $sendAs
        sendOnBehalfTo = $sendOnBehalf
        fullAccessCount = @($fullAccess).Count
        sendAsCount = @($sendAs).Count
        sendOnBehalfCount = @($sendOnBehalf).Count
        delegationsFound = ((@($fullAccess).Count + @($sendAs).Count + @($sendOnBehalf).Count) -gt 0)
        source = "Exchange Online PowerShell live"
        tried = $tried
    }

    $response | ConvertTo-Json -Depth 10 -Compress
    Disconnect-Safely
    exit 0
}
catch {
    Disconnect-Safely
    $errorResponse = [ordered]@{
        enabled = $true
        configured = $true
        available = $false
        found = $false
        error = $_.Exception.Message
        source = "Exchange Online PowerShell live"
    }
    $errorResponse | ConvertTo-Json -Depth 8 -Compress
    exit 0
}
