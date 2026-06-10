# V5 - Export PDF

Cette version ajoute :

- Export PDF d'une fiche compte : `GET /api/account/pdf?identifier=...`
- Export PDF d'une analyse en lot : `POST /api/batch/export-pdf`
- Boutons dans l'interface : `Exporter PDF fiche` et `Exporter PDF lot`

## Points inclus dans le PDF fiche

- Conclusion, score, risque, confiance
- Identite Entra ID
- Synchronisation on-premise
- Sign-in activity et activite Microsoft 365
- Exchange Online : type de destinataire, boite partagee, taille, dernier logon, delegations
- MFA / methodes d'authentification
- Proprietaire probable / manager
- Licences
- Alias / proxyAddresses
- Signaux exploites
- Groupes et roles
- Avertissements

## Installation

La dependance ajoutee est :

```text
reportlab==4.2.5
```

Apres installation ou remplacement du projet :

```powershell
.\start.ps1
```

Puis dans le navigateur :

```text
CTRL + F5
```

## Note

Le PDF est fait pour l'archivage et la transmission. Pour filtrer, trier ou retraiter les donnees, l'export Excel reste plus adapte.
