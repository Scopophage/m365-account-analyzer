from __future__ import annotations

import csv
import io
import json
import time
from typing import Any

from .config import settings
from .graph_client import GraphApiError, GraphClient


USER_SELECT = ",".join(
    [
        "id",
        "displayName",
        "userPrincipalName",
        "mail",
        "accountEnabled",
        "userType",
        "createdDateTime",
        "jobTitle",
        "department",
        "companyName",
        "officeLocation",
        "mobilePhone",
        "businessPhones",
        "employeeId",
        "employeeType",
        "assignedLicenses",
        "licenseAssignmentStates",
        "onPremisesSyncEnabled",
        "onPremisesLastSyncDateTime",
        "onPremisesSamAccountName",
        "onPremisesDistinguishedName",
        "onPremisesDomainName",
        "onPremisesUserPrincipalName",
        "proxyAddresses",
        "passwordPolicies",
        "lastPasswordChangeDateTime",
        "signInActivity",
    ]
)

GROUP_SELECT = ",".join(
    [
        "id",
        "displayName",
        "mail",
        "mailEnabled",
        "securityEnabled",
        "groupTypes",
        "description",
    ]
)

CONTACT_SELECT = ",".join(["id", "displayName", "mail", "mailNickname", "proxyAddresses"])


class M365DataService:
    def __init__(self, graph: GraphClient) -> None:
        self.graph = graph

    def find_user(self, identifier: str) -> tuple[dict[str, Any], list[str]]:
        identifier = identifier.strip()
        warnings: list[str] = []
        if not identifier:
            raise GraphApiError("Identifiant vide.", 400)

        lowered = identifier.lower()
        escaped = self.graph.escape_odata_string(identifier)
        escaped_lower = self.graph.escape_odata_string(lowered)

        # 1) Acces direct : fonctionne avec id objet ou UPN exact.
        # On evite cette tentative quand il y a des espaces, car ce n'est pas un id/UPN valide.
        if " " not in identifier:
            try:
                user = self.graph.get(
                    f"/users/{self.graph.quote_id(identifier)}",
                    params={"$select": USER_SELECT},
                )
                if user.get("id"):
                    return user, warnings
            except GraphApiError as exc:
                if exc.status_code not in {400, 404}:
                    warnings.append(str(exc))

        # 2) Filtres exacts : UPN, mail, samAccountName local, nom affiche exact.
        filters = [
            f"userPrincipalName eq '{escaped}'",
            f"mail eq '{escaped}'",
            f"onPremisesSamAccountName eq '{escaped}'",
            f"displayName eq '{escaped}'",
        ]

        # 3) Alias Exchange / proxyAddresses. Tres utile quand l'adresse cherchee est un alias.
        if "@" in identifier:
            filters.extend(
                [
                    f"proxyAddresses/any(p:p eq 'SMTP:{escaped}')",
                    f"proxyAddresses/any(p:p eq 'smtp:{escaped}')",
                    f"proxyAddresses/any(p:p eq 'SMTP:{escaped_lower}')",
                    f"proxyAddresses/any(p:p eq 'smtp:{escaped_lower}')",
                ]
            )

        for filter_expression in filters:
            try:
                result = self.graph.get(
                    "/users",
                    params={
                        "$select": USER_SELECT,
                        "$filter": filter_expression,
                        "$top": 10,
                    },
                )
                values = result.get("value", [])
                if values:
                    if len(values) > 1:
                        warnings.append("Plusieurs utilisateurs correspondent au filtre exact : premier resultat retourne.")
                    return values[0], warnings
            except GraphApiError as exc:
                warnings.append(f"Recherche avec filtre ignoree ({filter_expression}) : {exc}")

        # 4) Recherche approximative par nom affiche et UPN. Necessite ConsistencyLevel eventual.
        # Utile pour saisir 'Support CONTOSO' au lieu de l'UPN.
        search_value = identifier.replace('"', "").strip()
        if search_value:
            for search_expression in [
                f'"displayName:{search_value}"',
                f'"userPrincipalName:{search_value}"',
                f'"mail:{search_value}"',
            ]:
                try:
                    result = self.graph.get(
                        "/users",
                        params={
                            "$select": USER_SELECT,
                            "$search": search_expression,
                            "$top": 10,
                            "$count": "true",
                        },
                        headers={"ConsistencyLevel": "eventual"},
                    )
                    values = result.get("value", [])
                    if values:
                        if len(values) > 1:
                            warnings.append("Recherche approximative : plusieurs resultats possibles, premier resultat retourne.")
                        else:
                            warnings.append("Utilisateur trouve via recherche approximative Graph.")
                        return values[0], warnings
                except GraphApiError as exc:
                    warnings.append(f"Recherche approximative ignoree ({search_expression}) : {exc}")

        # 5) Aide au diagnostic : existe peut-etre en groupe/contact au lieu d'utilisateur.
        object_hints = self.find_non_user_hints(identifier)
        if object_hints:
            warnings.append("Aucun user trouve, mais un objet non utilisateur correspondant existe peut-etre : " + object_hints)

        raise GraphApiError(f"Aucun utilisateur trouve pour : {identifier}", 404, {"warnings": warnings})

    def find_non_user_hints(self, identifier: str) -> str:
        hints: list[str] = []
        escaped = self.graph.escape_odata_string(identifier)
        lower = self.graph.escape_odata_string(identifier.lower())

        try:
            group_filters = [f"mail eq '{escaped}'", f"displayName eq '{escaped}'"]
            if "@" in identifier:
                group_filters.extend(
                    [
                        f"proxyAddresses/any(p:p eq 'SMTP:{escaped}')",
                        f"proxyAddresses/any(p:p eq 'smtp:{escaped}')",
                        f"proxyAddresses/any(p:p eq 'SMTP:{lower}')",
                        f"proxyAddresses/any(p:p eq 'smtp:{lower}')",
                    ]
                )
            for filter_expression in group_filters:
                result = self.graph.get(
                    "/groups",
                    params={"$select": GROUP_SELECT, "$filter": filter_expression, "$top": 3},
                )
                values = result.get("value", [])
                for item in values:
                    hints.append(f"groupe '{item.get('displayName')}' ({item.get('mail') or item.get('id')})")
                if hints:
                    break
        except GraphApiError:
            pass

        try:
            contact_filters = [f"mail eq '{escaped}'", f"displayName eq '{escaped}'"]
            if "@" in identifier:
                contact_filters.extend(
                    [
                        f"proxyAddresses/any(p:p eq 'SMTP:{escaped}')",
                        f"proxyAddresses/any(p:p eq 'smtp:{escaped}')",
                        f"proxyAddresses/any(p:p eq 'SMTP:{lower}')",
                        f"proxyAddresses/any(p:p eq 'smtp:{lower}')",
                    ]
                )
            for filter_expression in contact_filters:
                result = self.graph.get(
                    "/contacts",
                    params={"$select": CONTACT_SELECT, "$filter": filter_expression, "$top": 3},
                )
                values = result.get("value", [])
                for item in values:
                    hints.append(f"contact '{item.get('displayName')}' ({item.get('mail') or item.get('id')})")
                if any("contact" in hint for hint in hints):
                    break
        except GraphApiError:
            pass

        return "; ".join(hints[:5])

    def get_member_of(self, user_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        try:
            items = self.graph.get_all(
                f"/users/{self.graph.quote_id(user_id)}/memberOf",
                params={"$top": 999},
                max_pages=10,
            )
            return items, warnings
        except GraphApiError as exc:
            warnings.append(
                "Impossible de lire les groupes/roles avec /memberOf. Verifie Directory.Read.All. " + str(exc)
            )
            return [], warnings

    def get_transitive_member_of(self, user_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        try:
            items = self.graph.get_all(
                f"/users/{self.graph.quote_id(user_id)}/transitiveMemberOf",
                params={"$top": 999},
                max_pages=20,
            )
            return items, warnings
        except GraphApiError as exc:
            warnings.append(
                "Impossible de lire les groupes/roles transitifs avec /transitiveMemberOf. "
                "Verifie Directory.Read.All. " + str(exc)
            )
            return [], warnings

    def get_authentication_methods(self, user_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        try:
            result = self.graph.get(f"/users/{self.graph.quote_id(user_id)}/authentication/methods")
            return result.get("value", []), warnings
        except GraphApiError as exc:
            warnings.append(
                "Impossible de lire les methodes MFA/authentication. "
                "Permission utile : UserAuthenticationMethod.Read.All. " + str(exc)
            )
            return [], warnings

    def get_manager(self, user_id: str) -> tuple[dict[str, Any] | None, list[str]]:
        warnings: list[str] = []
        try:
            manager = self.graph.get(
                f"/users/{self.graph.quote_id(user_id)}/manager",
                params={"$select": "id,displayName,userPrincipalName,mail,jobTitle,department"},
            )
            return manager, warnings
        except GraphApiError as exc:
            if exc.status_code != 404:
                warnings.append("Impossible de lire le manager. Verifie Directory.Read.All. " + str(exc))
            return None, warnings

    def get_owned_objects(self, user_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        try:
            items = self.graph.get_all(
                f"/users/{self.graph.quote_id(user_id)}/ownedObjects",
                params={"$top": 999},
                max_pages=5,
            )
            return items, warnings
        except GraphApiError as exc:
            warnings.append("Impossible de lire les objets possedes. Verifie Directory.Read.All. " + str(exc))
            return [], warnings

    def get_recent_signins(self, user_id: str, user_principal_name: str | None = None, top: int = 10) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        select = ",".join(
            [
                "createdDateTime",
                "appDisplayName",
                "resourceDisplayName",
                "clientAppUsed",
                "ipAddress",
                "isInteractive",
                "conditionalAccessStatus",
                "status",
                "location",
                "userPrincipalName",
                "userId",
            ]
        )
        filters = [f"userId eq '{self.graph.escape_odata_string(user_id)}'"]
        if user_principal_name:
            filters.append(f"userPrincipalName eq '{self.graph.escape_odata_string(user_principal_name)}'")

        for filter_expression in filters:
            params = {
                "$filter": filter_expression,
                "$top": min(max(top, 1), 50),
                "$orderby": "createdDateTime desc",
                "$select": select,
            }
            try:
                result = self.graph.get("/auditLogs/signIns", params=params)
                return result.get("value", []), warnings
            except GraphApiError as exc:
                try:
                    params.pop("$orderby", None)
                    result = self.graph.get("/auditLogs/signIns", params=params)
                    warnings.append("La requete signIns a ete executee sans $orderby.")
                    return result.get("value", []), warnings
                except GraphApiError:
                    warnings.append(
                        f"Impossible de lire les derniers sign-ins avec le filtre {filter_expression}. "
                        "Verifie AuditLog.Read.All, les roles et la retention Entra. " + str(exc)
                    )
        return [], warnings

    def get_subscribed_skus(self) -> tuple[dict[str, dict[str, Any]], list[str]]:
        warnings: list[str] = []
        cache_path = settings.cache_dir / "subscribed_skus.json"
        ttl_seconds = max(settings.report_cache_hours, 1) * 3600

        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl_seconds:
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                return {str(item.get("skuId")).lower(): item for item in cached}, warnings
            except (ValueError, OSError):
                pass

        try:
            # Important : /subscribedSkus ne supporte pas $top custom.
            items = self.graph.get_all("/subscribedSkus", params=None, max_pages=5)
            try:
                cache_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
            return {str(item.get("skuId")).lower(): item for item in items}, warnings
        except GraphApiError as exc:
            warnings.append(
                "Impossible de lire /subscribedSkus. Les licences seront affichees avec leurs GUID. "
                "Permission utile : LicenseAssignment.Read.All ou Directory.Read.All. "
                + str(exc)
            )
            return {}, warnings

    def get_office365_active_user_detail(self, period: str | None = None) -> tuple[list[dict[str, str]], list[str]]:
        warnings: list[str] = []
        if not settings.enable_reports:
            return [], ["Graph Reports desactive via ENABLE_REPORTS=false."]

        period = (period or settings.graph_period).upper()
        if period not in {"D7", "D30", "D90", "D180"}:
            period = "D180"

        cache_path = settings.cache_dir / f"office365_active_user_detail_{period}.csv"
        ttl_seconds = max(settings.report_cache_hours, 1) * 3600
        csv_text: str | None = None

        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl_seconds:
            try:
                csv_text = cache_path.read_text(encoding="utf-8-sig")
            except OSError:
                csv_text = None

        if csv_text is None:
            try:
                csv_text = self.graph.download_report_csv(f"/reports/getOffice365ActiveUserDetail(period='{period}')")
                try:
                    cache_path.write_text(csv_text, encoding="utf-8")
                except OSError:
                    warnings.append("Rapport telecharge mais impossible d'ecrire le cache local.")
            except GraphApiError as exc:
                warnings.append(
                    "Impossible de lire Graph Reports getOffice365ActiveUserDetail. Verifie Reports.Read.All. " + str(exc)
                )
                return [], warnings

        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader), warnings

    def get_activity_report_for_user(self, upn: str, mail: str | None = None) -> tuple[dict[str, str] | None, list[str]]:
        rows, warnings = self.get_office365_active_user_detail()
        if not rows:
            return None, warnings

        candidates = {upn.strip().lower()}
        if mail:
            candidates.add(mail.strip().lower())

        for row in rows:
            row_upn = (row.get("User Principal Name") or "").strip().lower()
            row_display = (row.get("Display Name") or "").strip().lower()
            row_mail = (row.get("Email Address") or row.get("Mail") or "").strip().lower()
            if row_upn in candidates or row_mail in candidates or row_display in candidates:
                return row, warnings

        warnings.append(
            "Aucune ligne trouvee dans le rapport Office 365 Active User Detail pour cet utilisateur. "
            "Ca peut etre normal si le compte n'a pas d'activite, si le compte n'est pas licence, ou si les rapports sont anonymises cote tenant."
        )
        return None, warnings

