[35m.env.example[m[36m:[m[1;31mTENANT[m_ID=00000000-0000-0000-0000-000000000000
[35m.env.example[m[36m:[m# Domaine primaire .onmicrosoft.com du [1;31mtenant[m, ex : adventiel.onmicrosoft.com
[35mREADME.md[m[36m:[mCette V1 est volontairement **[1;31mtenant[m-only** : elle n'interroge pas directement l'Active Directory local, les contrôleurs de domaine ou les serveurs Windows.
[35mREADME.md[m[36m:[mDirectory ([1;31mtenant[m) ID
[35mREADME.md[m[36m:[mGrant admin consent for <[1;31mtenant[m>
[35mREADME.md[m[36m:[m[1;31mTENANT[m_ID=ton_[1;31mtenant[m_id
[35mREADME.md[m[36m:[m| Catalogue des licences [1;31mtenant[m | `GET /subscribedSkus` |
[35mREADME.md[m[36m:[m- `[1;31mTENANT[m_ID` ;
[35mREADME.md[m[36m:[m- les rapports d'utilisation sont anonymisés côté [1;31mtenant[m ;
[35mapp/analyzer.py[m[36m:[m            reasons.append("Compte synchronise depuis l'AD local vers le [1;31mtenant[m.")
[35mapp/analyzer.py[m[36m:[m            reasons.append(f"{licenses['count']} licence(s) affectee(s) cote [1;31mtenant[m.")
[35mapp/analyzer.py[m[36m:[m            "[1;31mtenant[mOnlyWarning": "Cette analyse couvre Microsoft 365 / Entra ID et, si active, Exchange Online. Elle ne prouve pas l'absence d'usage local on-premise.",
[35mapp/config.py[m[36m:[m    [1;31mtenant[m_id: str
[35mapp/config.py[m[36m:[m            [1;31mtenant[m_id=os.getenv("[1;31mTENANT[m_ID", "").strip(),
[35mapp/config.py[m[36m:[m        if not self.[1;31mtenant[m_id:
[35mapp/config.py[m[36m:[m            missing.append("[1;31mTENANT[m_ID")
[35mapp/graph_client.py[m[36m:[m        authority = f"https://login.microsoftonline.com/{settings.[1;31mtenant[m_id}"
[35mapp/graph_client.py[m[36m:[m                "Impossible d'obtenir un jeton Microsoft Graph. Vérifie le [1;31mtenant[m, le client ID, le secret et le consentement admin.",
[35mapp/main.py[m[36m:[m    description="Analyse [1;31mtenant[m-only Microsoft 365 / Entra ID pour qualifier l'usage d'un compte.",
[35mapp/main.py[m[36m:[m            "Licences [1;31mtenant[m / subscribedSkus",
[35mapp/services.py[m[36m:[m            "Ca peut etre normal si le compte n'a pas d'activite, si le compte n'est pas licence, ou si les rapports sont anonymises cote [1;31mtenant[m."
[35mapp/static/app.js[m[36m:[m    sourceCoverage.subscribedSkus ? 'Licences [1;31mtenant[m lisibles' : 'Licences [1;31mtenant[m non lues',
[35mapp/static/app.js[m[36m:[m      <p>${escapeHtml(conclusion.[1;31mtenant[mOnlyWarning || '')}</p>
[35mapp/static/index.html[m[36m:[m      <p>Analyse [1;31mtenant[m-only Microsoft 365 / Entra ID par UPN, mail, alias, nom ou samAccountName synchronise.</p>
[35mdocs/GRAPH_APIS_ET_PERMISSIONS.md[m[36m:[m### Licence [1;31mtenant[m
[35mstart.bat[m[36m:[m  echo Fichier .env cree. Renseigne [1;31mTENANT[m_ID, CLIENT_ID et CLIENT_SECRET puis relance.
[35mstart.ps1[m[36m:[m    Write-Host "Fichier .env cree. Renseigne [1;31mTENANT[m_ID, CLIENT_ID et CLIENT_SECRET puis relance." -ForegroundColor Yellow
