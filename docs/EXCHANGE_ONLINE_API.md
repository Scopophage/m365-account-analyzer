# V4 - Exchange Online live API

Cette V4 ajoute une lecture **Exchange Online live** depuis l'application locale.

Elle permet de savoir si l'adresse correspond à :

- une boîte utilisateur (`UserMailbox`) ;
- une boîte partagée (`SharedMailbox`) ;
- une salle (`RoomMailbox`) ;
- un équipement (`EquipmentMailbox`) ;
- un objet mail sans boîte via `Get-EXORecipient` ;
- les délégations `Full Access`, `Send As` et `Send on behalf` ;
- la taille, le nombre d'éléments, `LastLogonTime` et `LastUserActionTime` quand disponibles.

## Principe technique

Microsoft Graph ne suffit pas pour ces informations Exchange détaillées. La V4 appelle donc le module PowerShell `ExchangeOnlineManagement` en backend local via le script :

```text
tools\exchange_lookup.ps1
```

L'application Python appelle ce script en live à chaque analyse, avec un petit cache local optionnel (`EXCHANGE_CACHE_MINUTES`) pour éviter de reconnecter trop souvent pendant les tests.

## Pré-requis PowerShell

Dans PowerShell :

```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
```

## Mode recommandé : app-only avec certificat

1. Crée ou réutilise une App registration Entra ID.
2. Ajoute l'API permission :

```text
APIs my organization uses
> Office 365 Exchange Online
> Application permissions
> Exchange.ManageAsApp
```

3. Fais `Grant admin consent`.
4. Assigne un rôle Entra à l'application, par exemple `Exchange Administrator` ou un rôle plus restreint si vous avez une délégation RBAC adaptée.
5. Génère un certificat local :

```powershell
.\tools\setup_exchange_certificate.ps1
```

6. Téléverse le fichier `.cer` généré dans :

```text
App registrations
> ton application
> Certificates & secrets
> Certificates
```

7. Mets à jour `.env` :

```env
ENABLE_EXCHANGE_ONLINE=true
EXCHANGE_AUTH_MODE=app_certificate
EXCHANGE_ORGANIZATION=adventiel.onmicrosoft.com
EXCHANGE_APP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EXCHANGE_CERTIFICATE_THUMBPRINT=THUMBPRINT_DU_CERTIFICAT
EXCHANGE_INCLUDE_PERMISSIONS=true
EXCHANGE_CACHE_MINUTES=30
EXCHANGE_TIMEOUT_SECONDS=120
```

## Mode de test : interactive

Pour tester sans certificat, tu peux utiliser :

```env
ENABLE_EXCHANGE_ONLINE=true
EXCHANGE_AUTH_MODE=interactive
EXCHANGE_ADMIN_UPN=ton.admin@adventiel.fr
EXCHANGE_ORGANIZATION=adventiel.onmicrosoft.com
```

Ce mode peut ouvrir une fenêtre de connexion et n'est pas idéal pour l'analyse en lot.

## Diagnostic

Dans l'application, clique sur :

```text
Tester la configuration
```

Tu dois voir :

```text
Exchange Online API / mailbox lookup : OK
```

Si ce test échoue, vérifie :

- le module `ExchangeOnlineManagement` ;
- `EXCHANGE_ORGANIZATION` avec le domaine `.onmicrosoft.com` ;
- `EXCHANGE_APP_ID` ;
- `EXCHANGE_CERTIFICATE_THUMBPRINT` ;
- le certificat installé dans `Cert:\CurrentUser\My` ;
- `Exchange.ManageAsApp` avec admin consent ;
- le rôle Exchange attribué à l'application.
