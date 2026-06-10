# Graph APIs et permissions nécessaires

## Permissions à accorder en Application permissions

| Permission | Obligatoire | Utilisation dans l'app |
|---|---:|---|
| `User.Read.All` | Oui | Lire les utilisateurs et leurs propriétés sélectionnées. |
| `Directory.Read.All` | Oui | Lire les objets d'annuaire, groupes, rôles directs et attributs directory. |
| `AuditLog.Read.All` | Oui | Lire `signInActivity` et `/auditLogs/signIns`. |
| `Reports.Read.All` | Oui | Lire `getOffice365ActiveUserDetail`. |
| `LicenseAssignment.Read.All` | Recommandé | Lire `/subscribedSkus` pour afficher les noms de licences. |

## Endpoints utilisés

### User lookup

```http
GET https://graph.microsoft.com/v1.0/users/{id-or-userPrincipalName}?$select=id,displayName,userPrincipalName,mail,accountEnabled,userType,createdDateTime,assignedLicenses,onPremisesSyncEnabled,onPremisesLastSyncDateTime,onPremisesSamAccountName,onPremisesDistinguishedName,onPremisesDomainName,onPremisesUserPrincipalName,proxyAddresses,passwordPolicies,lastPasswordChangeDateTime,signInActivity
```

### Recherche alternative

```http
GET https://graph.microsoft.com/v1.0/users?$filter=userPrincipalName eq '{identifier}'
GET https://graph.microsoft.com/v1.0/users?$filter=mail eq '{identifier}'
GET https://graph.microsoft.com/v1.0/users?$filter=onPremisesSamAccountName eq '{identifier}'
```

### Recherche par nom affiché

```http
GET https://graph.microsoft.com/v1.0/users?$search="displayName:{identifier}"&$count=true
ConsistencyLevel: eventual
```

### Groupes et rôles directs

```http
GET https://graph.microsoft.com/v1.0/users/{id}/memberOf?$top=999
```

### Derniers sign-ins

```http
GET https://graph.microsoft.com/v1.0/auditLogs/signIns?$filter=userId eq '{id}'&$top=10&$orderby=createdDateTime desc
```

### Activité Microsoft 365

```http
GET https://graph.microsoft.com/v1.0/reports/getOffice365ActiveUserDetail(period='D180')
```

L'API renvoie un 302 vers une URL temporaire de téléchargement CSV. Le code suit cette redirection et met le CSV en cache local.

### Licence tenant

```http
GET https://graph.microsoft.com/v1.0/subscribedSkus
```

Sert à convertir les `skuId` de `assignedLicenses` en `skuPartNumber` plus lisibles.
