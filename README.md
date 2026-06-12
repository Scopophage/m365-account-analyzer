# M365 Account Analyzer

Application web locale pour analyser l'usage Microsoft 365 / Entra ID d'un compte utilisateur à partir d'un identifiant : UPN, adresse mail, id objet Entra ou `samAccountName` local synchronisé.

The application is tenant-focused and does not directly query on-premises Active Directory.

## Ce que l'application affiche

- identité Entra ID : nom, UPN, mail, compte activé, type, date de création ;
- attributs hybrides synchronisés : `onPremisesSyncEnabled`, `onPremisesSamAccountName`, `onPremisesLastSyncDateTime`, DN local ;
- dernières connexions via `signInActivity` ;
- derniers sign-ins disponibles via `/auditLogs/signIns` ;
- activité Microsoft 365 via Graph Reports : Exchange, OneDrive, SharePoint, Teams ;
- licences affectées via `assignedLicenses` + correspondance `/subscribedSkus` ;
- groupes et rôles d'annuaire directs via `/memberOf` ;
- conclusion automatique : actif confirmé, actif non interactif, compte technique probable, candidat revue, compte critique potentiel.

## Limite importante

L'application indique : **aucun usage Microsoft 365 détecté**.

Elle ne prouve pas qu'un compte n'est pas utilisé localement sur un serveur, un service Windows, une tâche planifiée, une application métier ou un script on-premise.

## Prérequis

- Windows avec VS Code.
- Python 3.11 ou plus récent.
- Droits administrateur Microsoft 365 / Entra suffisants pour créer une inscription d'application et accorder le consentement admin.
- Idéalement Microsoft Entra ID P1/P2 pour exploiter correctement les journaux/signaux de connexion.

## 1. Ouvrir le projet dans VS Code

Dézippe le projet, puis ouvre le dossier `m365-account-analyzer` dans VS Code.

## 2. Créer l'inscription d'application Entra ID

Va dans :

```text
Microsoft Entra admin center
> Applications
> App registrations
> New registration
```

Paramètres conseillés :

```text
Name: M365 Account Analyzer
Supported account types: Accounts in this organizational directory only
Redirect URI: vide
```

Après création, note :

```text
Application (client) ID
Directory (tenant) ID
```

Ensuite :

```text
Certificates & secrets
> New client secret
```

Copie immédiatement la valeur du secret, pas seulement son ID.

## 3. Ajouter les permissions Microsoft Graph

Dans l'inscription d'application :

```text
API permissions
> Add a permission
> Microsoft Graph
> Application permissions
```

Ajoute ces permissions :

| Permission | Pourquoi |
|---|---|
| `User.Read.All` | Lire les profils utilisateurs et leurs propriétés de base. |
| `Directory.Read.All` | Lire groupes, rôles, propriétés d'annuaire et memberships. |
| `AuditLog.Read.All` | Lire `signInActivity` et les derniers sign-ins. |
| `Reports.Read.All` | Lire les rapports d'activité Microsoft 365. |
| `LicenseAssignment.Read.All` | Lire `/subscribedSkus` pour convertir les GUID de licences en noms lisibles. |

Clique ensuite sur :

```text
Grant admin consent for <tenant>
```

## 4. Configurer le fichier `.env`

Copie le fichier `.env.example` en `.env`.

Sous PowerShell :

```powershell
Copy-Item .env.example .env
```

Puis édite `.env` :

```env
TENANT_ID=ton_tenant_id
CLIENT_ID=ton_client_id
CLIENT_SECRET=ton_secret_client
GRAPH_PERIOD=D180
REPORT_CACHE_HOURS=12
ENABLE_REPORTS=true
```

Ne partage jamais le fichier `.env`.

## 5. Lancer l'application

Dans le terminal VS Code, depuis le dossier du projet :

```powershell
.\start.ps1
```

Si PowerShell bloque les scripts, utilise :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```

Alternative sans script :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Puis ouvre :

```text
http://127.0.0.1:8000
```

## 6. Utilisation

Recherche simple :

```text
service.account@contoso.com
```

Analyse en lot : colle une liste avec un identifiant par ligne.

Tu peux aussi importer un CSV avec une colonne nommée par exemple :

```text
Identifiant (UPN)
UPN
UserPrincipalName
Adresse Email
Email
mail
samAccountName
Nom complet
```

## APIs Microsoft Graph utilisées

| Fonction | Endpoint |
|---|---|
| Trouver un utilisateur | `GET /users/{id-or-upn}` |
| Recherche par UPN, mail ou samAccountName | `GET /users?$filter=...` |
| Lire les attributs hybrides et `signInActivity` | `GET /users/{id}?$select=...` |
| Groupes/rôles directs | `GET /users/{id}/memberOf` |
| Derniers sign-ins | `GET /auditLogs/signIns?$filter=userId eq '...'` |
| Rapport activité M365 | `GET /reports/getOffice365ActiveUserDetail(period='D180')` |
| Catalogue des licences tenant | `GET /subscribedSkus` |

## Pourquoi l'application n'utilise pas `/users/{id}/licenseDetails`

L'API `GET /users/{id}/licenseDetails` est pratique en mode délégué, mais sa documentation indique que les permissions d'application ne sont pas supportées pour cette opération. Comme cette application fonctionne côté serveur avec un secret applicatif et sans connexion utilisateur, elle utilise plutôt :

- `assignedLicenses` sur l'objet user ;
- `/subscribedSkus` pour traduire les `skuId` en `skuPartNumber` ;
- le rapport `getOffice365ActiveUserDetail` pour les produits affectés et les licences de services.

## Sécurité

Cette application utilise le flux client credentials : elle agit avec l'identité de l'application et non avec l'identité de l'utilisateur connecté.

Pour une V5 locale admin, lance-la uniquement en local :

```text
127.0.0.1:8000
```

Ne l'expose pas directement sur Internet.

Si tu veux la déployer pour plusieurs admins, ajoute avant tout :

- authentification Entra ID devant l'application ;
- restriction réseau/VPN ;
- journalisation des recherches ;
- rotation du secret ou certificat au lieu d'un secret long terme ;
- principe du moindre privilège sur les permissions Graph.

## Dépannage rapide

### Erreur 401 / invalid_client

Vérifie :

- `TENANT_ID` ;
- `CLIENT_ID` ;
- `CLIENT_SECRET` ;
- secret expiré ou mauvaise valeur copiée.

### Erreur 403 / Authorization_RequestDenied

Vérifie :

- permissions Graph ajoutées en **Application permissions**, pas Delegated ;
- consentement admin accordé ;
- rôle/licence nécessaire pour les journaux de connexion.

### Le rapport Microsoft 365 ne trouve pas l'utilisateur

Ca peut arriver si :

- le compte n'a pas d'activité dans la période D180 ;
- les rapports d'utilisation sont anonymisés côté tenant ;
- `Reports.Read.All` n'a pas été consenti ;
- le cache local est ancien : supprime les CSV dans le dossier `cache`.

### Les noms de licences sont des GUID

Ajoute ou vérifie la permission `LicenseAssignment.Read.All`, puis relance l'application.

## Prochaines évolutions possibles

- authentification Entra ID pour les admins
- historique des recherches et décisions
- analyse des Enterprise Applications / permissions API
- audit Purview / Management Activity API
- déploiement Docker / IIS

## V4 - Option Exchange Online live API

La V4 ajoute une option `ENABLE_EXCHANGE_ONLINE=true` pour interroger Exchange Online en live depuis l'application locale.

Cette option ajoute dans la fiche compte :

- type Exchange : `UserMailbox`, `SharedMailbox`, `RoomMailbox`, `EquipmentMailbox`, etc. ;
- détection boîte partagée ;
- SMTP principal et alias Exchange ;
- taille de boîte et nombre d'éléments ;
- `LastLogonTime` et `LastUserActionTime` si retournés par Exchange ;
- délégations `Full Access`, `Send As` et `Send on behalf` ;
- colonnes Exchange dans le CSV et l'export Excel.

Documentation détaillée :

```text
docs/EXCHANGE_ONLINE_API.md
```

### Démarrage rapide Exchange

Installer le module :

```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
```

Mode test interactif :

```env
ENABLE_EXCHANGE_ONLINE=true
EXCHANGE_AUTH_MODE=interactive
EXCHANGE_ADMIN_UPN=admin@contoso.com
EXCHANGE_ORGANIZATION=contoso.onmicrosoft.com
```

Mode recommandé app-only certificat :

```powershell
.\tools\setup_exchange_certificate.ps1
```

Puis renseigner dans `.env` :

```env
ENABLE_EXCHANGE_ONLINE=true
EXCHANGE_AUTH_MODE=app_certificate
EXCHANGE_ORGANIZATION=contoso.onmicrosoft.com
EXCHANGE_APP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EXCHANGE_CERTIFICATE_THUMBPRINT=THUMBPRINT_DU_CERTIFICAT
EXCHANGE_INCLUDE_PERMISSIONS=true
```

## V5 - Export PDF

La V5 ajoute deux exports PDF :

- `Exporter PDF fiche` apres une recherche simple.
- `Exporter PDF lot` apres une analyse en lot.

Le PDF fiche contient la conclusion, les donnees Entra ID, l'activite M365, Exchange Online, MFA, groupes, roles, delegations Exchange, signaux exploites et avertissements.

Le PDF lot est une synthese imprimable. Pour filtrer et retraiter les donnees, utilise aussi l'export Excel.

Dependance ajoutee :

```text
reportlab==4.2.5
```

Apres remplacement du projet ou ajout de la V5, lance :

```powershell
.\start.ps1
```

Puis force le rechargement du navigateur avec `CTRL + F5`.

