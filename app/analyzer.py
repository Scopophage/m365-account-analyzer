from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from .exchange_service import ExchangeOnlineService
from .graph_client import GraphClient
from .services import M365DataService


SERVICE_OR_CRITICAL_KEYWORDS = [
    "sync_",
    "adconnect",
    "ad connect",
    "aadconnect",
    "aadsync",
    "entra connect",
    "directory synchronization",
    "directory synchronisation",
    "on-premises directory synchronization",
    "azure ad connect",
]

TECHNICAL_KEYWORDS = [
    "svc",
    "service",
    "bot",
    "robot",
    "veeam",
    "backup",
    "cloudally",
    "devops",
    "sso",
    "sync",
    "sharepoint",
    "intranet",
    "test",
    "talentia",
    "mco",
    "infogerance",
    "infogérance",
    "ct_",
    "compte.",
    "compte ",
    "ecriture",
    "écriture",
    "event",
    "evenement",
    "événement",
]

LOW_VALUE_GROUP_NAMES = {
    "tous les utilisateurs",
    "all users",
    "adventiel",
}

PRIVILEGED_ROLE_KEYWORDS = [
    "global administrator",
    "privileged role administrator",
    "security administrator",
    "exchange administrator",
    "sharepoint administrator",
    "user administrator",
    "authentication administrator",
    "intune administrator",
    "directory writers",
]

MFA_METHOD_TYPES = {
    "microsoftAuthenticatorAuthenticationMethod": "Microsoft Authenticator",
    "phoneAuthenticationMethod": "Telephone",
    "fido2AuthenticationMethod": "FIDO2",
    "windowsHelloForBusinessAuthenticationMethod": "Windows Hello",
    "temporaryAccessPassAuthenticationMethod": "Temporary Access Pass",
    "emailAuthenticationMethod": "Email",
    "softwareOathAuthenticationMethod": "OATH logiciel",
    "passwordAuthenticationMethod": "Mot de passe",
}

ACTIVITY_COLUMNS = [
    "Exchange Last Activity Date",
    "OneDrive Last Activity Date",
    "SharePoint Last Activity Date",
    "Teams Last Activity Date",
    "Skype For Business Last Activity Date",
    "Yammer Last Activity Date",
]


def parse_graph_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.startswith("/Date("):
            match = re.search(r"/Date\((\d+)", value)
            if match:
                return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except (ValueError, OSError):
        return None


def parse_report_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return parse_graph_datetime(value)


def days_since(date_value: datetime | None) -> int | None:
    if date_value is None:
        return None
    now = datetime.now(timezone.utc)
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return max((now - date_value).days, 0)


def compact_graph_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: compact_graph_object(v) for k, v in value.items() if not k.startswith("@odata")}
    if isinstance(value, list):
        return [compact_graph_object(item) for item in value]
    return value


class AccountAnalyzer:
    def __init__(self) -> None:
        self.graph = GraphClient()
        self.service = M365DataService(self.graph)
        self.exchange = ExchangeOnlineService()

    def analyze(self, identifier: str) -> dict[str, Any]:
        warnings: list[str] = []
        user, user_warnings = self.service.find_user(identifier)
        warnings.extend(user_warnings)

        member_of, member_warnings = self.service.get_member_of(user["id"])
        warnings.extend(member_warnings)

        transitive_member_of, transitive_warnings = self.service.get_transitive_member_of(user["id"])
        warnings.extend(transitive_warnings)

        auth_methods, auth_warnings = self.service.get_authentication_methods(user["id"])
        warnings.extend(auth_warnings)

        manager, manager_warnings = self.service.get_manager(user["id"])
        warnings.extend(manager_warnings)

        owned_objects, owned_warnings = self.service.get_owned_objects(user["id"])
        warnings.extend(owned_warnings)

        signins, signin_warnings = self.service.get_recent_signins(
            user["id"], user.get("userPrincipalName"), top=10
        )
        warnings.extend(signin_warnings)

        sku_map, sku_warnings = self.service.get_subscribed_skus()
        warnings.extend(sku_warnings)

        report_row, report_warnings = self.service.get_activity_report_for_user(
            user.get("userPrincipalName") or "",
            user.get("mail"),
        )
        warnings.extend(report_warnings)

        exchange, exchange_warnings = self.exchange.lookup_for_user(identifier, user)
        warnings.extend(exchange_warnings)

        licenses = self._build_license_summary(user, sku_map, report_row)
        memberships = self._build_memberships(member_of, transitive_member_of)
        security = self._build_security_summary(auth_methods, memberships)
        ownership = self._build_ownership(manager, owned_objects, user)
        signals = self._build_signals(user, report_row, signins, exchange)
        conclusion = self._build_conclusion(user, report_row, signals, licenses, memberships, security, exchange)

        return {
            "searchedIdentifier": identifier,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "identity": self._build_identity(user),
            "signInActivity": compact_graph_object(user.get("signInActivity") or {}),
            "recentSignIns": self._build_recent_signins(signins),
            "m365Activity": self._build_m365_activity(report_row),
            "licenses": licenses,
            "memberships": memberships,
            "security": security,
            "ownership": ownership,
            "exchange": exchange,
            "signals": signals,
            "conclusion": conclusion,
            "warnings": warnings,
            "sourceCoverage": {
                "graphUser": True,
                "memberOf": bool(member_of),
                "transitiveMemberOf": bool(transitive_member_of),
                "authenticationMethods": bool(auth_methods),
                "manager": manager is not None,
                "ownedObjects": bool(owned_objects),
                "signInLogs": bool(signins),
                "subscribedSkus": bool(sku_map),
                "office365ActiveUserDetail": report_row is not None,
                "exchangeOnline": bool(exchange.get("found") or exchange.get("recipientFound")),
            },
        }

    def _build_identity(self, user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user.get("id"),
            "displayName": user.get("displayName"),
            "userPrincipalName": user.get("userPrincipalName"),
            "mail": user.get("mail"),
            "accountEnabled": user.get("accountEnabled"),
            "userType": user.get("userType"),
            "createdDateTime": user.get("createdDateTime"),
            "jobTitle": user.get("jobTitle"),
            "department": user.get("department"),
            "companyName": user.get("companyName"),
            "officeLocation": user.get("officeLocation"),
            "mobilePhone": user.get("mobilePhone"),
            "businessPhones": user.get("businessPhones") or [],
            "employeeId": user.get("employeeId"),
            "employeeType": user.get("employeeType"),
            "passwordPolicies": user.get("passwordPolicies"),
            "lastPasswordChangeDateTime": user.get("lastPasswordChangeDateTime"),
            "proxyAddresses": user.get("proxyAddresses") or [],
            "onPremises": {
                "syncEnabled": user.get("onPremisesSyncEnabled"),
                "lastSyncDateTime": user.get("onPremisesLastSyncDateTime"),
                "samAccountName": user.get("onPremisesSamAccountName"),
                "distinguishedName": user.get("onPremisesDistinguishedName"),
                "domainName": user.get("onPremisesDomainName"),
                "userPrincipalName": user.get("onPremisesUserPrincipalName"),
            },
        }

    def _build_license_summary(
        self,
        user: dict[str, Any],
        sku_map: dict[str, dict[str, Any]],
        report_row: dict[str, str] | None,
    ) -> dict[str, Any]:
        assigned = user.get("assignedLicenses") or []
        mapped = []
        for lic in assigned:
            sku_id = str(lic.get("skuId", "")).lower()
            sku = sku_map.get(sku_id)
            mapped.append(
                {
                    "skuId": lic.get("skuId"),
                    "skuPartNumber": sku.get("skuPartNumber") if sku else None,
                    "disabledPlans": lic.get("disabledPlans") or [],
                }
            )

        report_products = []
        if report_row and report_row.get("Assigned Products"):
            report_products = [item.strip() for item in report_row["Assigned Products"].split("+") if item.strip()]

        service_flags = {
            "exchange": self._report_bool(report_row, "Has Exchange License"),
            "oneDrive": self._report_bool(report_row, "Has OneDrive License"),
            "sharePoint": self._report_bool(report_row, "Has SharePoint License"),
            "teams": self._report_bool(report_row, "Has Teams License"),
        }

        return {
            "count": len(assigned),
            "items": mapped,
            "assignedProductsFromReport": report_products,
            "hasExchangeLicense": service_flags["exchange"],
            "hasOneDriveLicense": service_flags["oneDrive"],
            "hasSharePointLicense": service_flags["sharePoint"],
            "hasTeamsLicense": service_flags["teams"],
            "hasAnyServiceLicense": any(value is True for value in service_flags.values()) or len(assigned) > 0,
        }

    def _build_memberships(self, member_of: list[dict[str, Any]], transitive_member_of: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        groups = []
        directory_roles = []
        admin_units = []
        other = []

        for item in member_of:
            odata_type = item.get("@odata.type", "")
            display_name = item.get("displayName")
            entry = {
                "id": item.get("id"),
                "displayName": display_name,
                "mail": item.get("mail"),
                "mailEnabled": item.get("mailEnabled"),
                "securityEnabled": item.get("securityEnabled"),
                "groupTypes": item.get("groupTypes") or [],
                "type": odata_type.replace("#microsoft.graph.", ""),
                "importance": self._group_importance(display_name, item),
            }
            if odata_type.endswith("group"):
                groups.append(entry)
            elif odata_type.endswith("directoryRole"):
                directory_roles.append(entry)
            elif odata_type.endswith("administrativeUnit"):
                admin_units.append(entry)
            else:
                other.append(entry)

        transitive_roles = []
        transitive_groups = []
        seen_direct_group_ids = {g.get("id") for g in groups}
        seen_direct_role_ids = {r.get("id") for r in directory_roles}
        for item in transitive_member_of or []:
            odata_type = item.get("@odata.type", "")
            entry = {
                "id": item.get("id"),
                "displayName": item.get("displayName"),
                "mail": item.get("mail"),
                "mailEnabled": item.get("mailEnabled"),
                "securityEnabled": item.get("securityEnabled"),
                "groupTypes": item.get("groupTypes") or [],
                "type": odata_type.replace("#microsoft.graph.", ""),
                "importance": self._group_importance(item.get("displayName"), item),
            }
            if odata_type.endswith("directoryRole") and item.get("id") not in seen_direct_role_ids:
                transitive_roles.append(entry)
            elif odata_type.endswith("group") and item.get("id") not in seen_direct_group_ids:
                transitive_groups.append(entry)

        all_roles = directory_roles + transitive_roles
        privileged_roles = [r for r in all_roles if self._is_privileged_role(r.get("displayName"))]
        groups.sort(key=lambda x: (x.get("importance") == "Standard", (x.get("displayName") or "").lower()))
        directory_roles.sort(key=lambda x: (x.get("displayName") or "").lower())
        transitive_roles.sort(key=lambda x: (x.get("displayName") or "").lower())
        return {
            "groupsCount": len(groups),
            "groups": groups,
            "transitiveGroupsCount": len(transitive_groups),
            "transitiveGroups": transitive_groups[:50],
            "directoryRolesCount": len(directory_roles),
            "directoryRoles": directory_roles,
            "transitiveDirectoryRolesCount": len(transitive_roles),
            "transitiveDirectoryRoles": transitive_roles,
            "allDirectoryRolesCount": len(all_roles),
            "privilegedRolesCount": len(privileged_roles),
            "privilegedRoles": privileged_roles,
            "isPrivileged": len(privileged_roles) > 0 or len(all_roles) > 0,
            "administrativeUnits": admin_units,
            "other": other,
        }


    def _build_security_summary(self, methods: list[dict[str, Any]], memberships: dict[str, Any]) -> dict[str, Any]:
        method_rows = []
        has_mfa = False
        strong_methods = []
        for method in methods or []:
            odata_type = (method.get("@odata.type") or "").replace("#microsoft.graph.", "")
            label = MFA_METHOD_TYPES.get(odata_type, odata_type or "Methode inconnue")
            row = {
                "id": method.get("id"),
                "type": odata_type,
                "label": label,
                "display": label,
            }
            if odata_type != "passwordAuthenticationMethod":
                has_mfa = True
                strong_methods.append(label)
            method_rows.append(row)

        role_names = [r.get("displayName") for r in (memberships.get("privilegedRoles") or []) if r.get("displayName")]
        return {
            "methodsReadable": bool(methods),
            "methodsCount": len(method_rows),
            "methods": method_rows,
            "hasMfaMethod": has_mfa,
            "strongMethods": sorted(set(strong_methods)),
            "isPrivileged": memberships.get("isPrivileged") is True,
            "privilegedRoles": role_names,
            "privilegedRolesCount": len(role_names),
            "mfaRecommendation": self._mfa_recommendation(has_mfa, memberships.get("isPrivileged") is True, bool(methods)),
        }

    def _build_ownership(self, manager: dict[str, Any] | None, owned_objects: list[dict[str, Any]], user: dict[str, Any]) -> dict[str, Any]:
        app_objects = []
        group_objects = []
        other_objects = []
        for item in owned_objects or []:
            odata_type = (item.get("@odata.type") or "").replace("#microsoft.graph.", "")
            row = {
                "id": item.get("id"),
                "displayName": item.get("displayName"),
                "appId": item.get("appId"),
                "type": odata_type,
            }
            if "application" in odata_type or item.get("appId"):
                app_objects.append(row)
            elif "group" in odata_type:
                group_objects.append(row)
            else:
                other_objects.append(row)

        probable_owner_parts = [
            user.get("department"),
            user.get("companyName"),
            user.get("officeLocation"),
        ]
        return {
            "manager": compact_graph_object(manager) if manager else None,
            "department": user.get("department"),
            "companyName": user.get("companyName"),
            "officeLocation": user.get("officeLocation"),
            "probableOwner": " / ".join([str(x) for x in probable_owner_parts if x]) or None,
            "ownedObjectsCount": len(owned_objects or []),
            "ownedApplications": app_objects[:20],
            "ownedGroups": group_objects[:20],
            "ownedOther": other_objects[:20],
        }

    def _build_recent_signins(self, signins: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for signin in signins:
            status = signin.get("status") or {}
            location = signin.get("location") or {}
            rows.append(
                {
                    "createdDateTime": signin.get("createdDateTime"),
                    "appDisplayName": signin.get("appDisplayName"),
                    "resourceDisplayName": signin.get("resourceDisplayName"),
                    "clientAppUsed": signin.get("clientAppUsed"),
                    "ipAddress": signin.get("ipAddress"),
                    "isInteractive": signin.get("isInteractive"),
                    "conditionalAccessStatus": signin.get("conditionalAccessStatus"),
                    "statusCode": status.get("errorCode"),
                    "statusFailureReason": status.get("failureReason"),
                    "statusAdditionalDetails": status.get("additionalDetails"),
                    "city": location.get("city"),
                    "countryOrRegion": location.get("countryOrRegion"),
                }
            )
        return rows

    def _build_m365_activity(self, report_row: dict[str, str] | None) -> dict[str, Any]:
        if not report_row:
            return {
                "found": False,
                "reportStatus": "Aucune ligne utilisateur dans le rapport M365 actif.",
            }

        return {
            "found": True,
            "reportStatus": "Ligne utilisateur trouvee dans le rapport M365 actif.",
            "reportRefreshDate": report_row.get("Report Refresh Date"),
            "isDeleted": report_row.get("Is Deleted"),
            "deletedDate": report_row.get("Deleted Date"),
            "exchangeLastActivityDate": report_row.get("Exchange Last Activity Date"),
            "oneDriveLastActivityDate": report_row.get("OneDrive Last Activity Date"),
            "sharePointLastActivityDate": report_row.get("SharePoint Last Activity Date"),
            "teamsLastActivityDate": report_row.get("Teams Last Activity Date"),
            "yammerLastActivityDate": report_row.get("Yammer Last Activity Date"),
            "skypeForBusinessLastActivityDate": report_row.get("Skype For Business Last Activity Date"),
        }

    def _build_signals(
        self,
        user: dict[str, Any],
        report_row: dict[str, str] | None,
        signins: list[dict[str, Any]],
        exchange: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        sign_in_activity = user.get("signInActivity") or {}

        for label, key in [
            ("Derniere connexion reussie", "lastSuccessfulSignInDateTime"),
            ("Derniere connexion interactive", "lastSignInDateTime"),
            ("Derniere connexion non interactive", "lastNonInteractiveSignInDateTime"),
        ]:
            dt = parse_graph_datetime(sign_in_activity.get(key))
            if dt:
                signals.append(
                    {
                        "name": label,
                        "date": dt.isoformat(),
                        "daysAgo": days_since(dt),
                        "source": "Microsoft Graph user.signInActivity",
                    }
                )

        if report_row:
            for column in ACTIVITY_COLUMNS:
                dt = parse_report_date(report_row.get(column))
                if dt:
                    signals.append(
                        {
                            "name": column.replace(" Last Activity Date", ""),
                            "date": dt.isoformat(),
                            "daysAgo": days_since(dt),
                            "source": "Microsoft Graph Reports getOffice365ActiveUserDetail",
                        }
                    )


        exchange = exchange or {}
        if exchange.get("hasMailbox"):
            for label, key in [
                ("Exchange derniere action utilisateur", "lastUserActionTime"),
                ("Exchange derniere interaction", "lastInteractionTime"),
                ("Exchange dernier logon boite", "lastLogonTime"),
            ]:
                dt = parse_graph_datetime(str(exchange.get(key))) if exchange.get(key) else None
                if dt:
                    signals.append(
                        {
                            "name": label,
                            "date": dt.isoformat(),
                            "daysAgo": days_since(dt),
                            "source": "Exchange Online PowerShell",
                        }
                    )

        for signin in signins:
            status = signin.get("status") or {}
            if status.get("errorCode") == 0:
                dt = parse_graph_datetime(signin.get("createdDateTime"))
                if dt:
                    signals.append(
                        {
                            "name": "Sign-in log reussi recent",
                            "date": dt.isoformat(),
                            "daysAgo": days_since(dt),
                            "source": "Microsoft Graph auditLogs/signIns",
                            "details": signin.get("appDisplayName"),
                        }
                    )
                    break

        signals.sort(key=lambda x: x.get("date") or "", reverse=True)
        return signals

    def _build_conclusion(
        self,
        user: dict[str, Any],
        report_row: dict[str, str] | None,
        signals: list[dict[str, Any]],
        licenses: dict[str, Any],
        memberships: dict[str, Any],
        security: dict[str, Any] | None = None,
        exchange: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        identity_text = " ".join(
            [
                str(user.get("displayName") or ""),
                str(user.get("userPrincipalName") or ""),
                str(user.get("mail") or ""),
                str(user.get("onPremisesSamAccountName") or ""),
                " ".join(user.get("proxyAddresses") or []),
            ]
        ).lower()

        security = security or {}
        exchange = exchange or {}
        exchange_found = exchange.get("found") is True or exchange.get("recipientFound") is True
        has_mailbox = exchange.get("hasMailbox") is True
        recipient_type = str(exchange.get("recipientTypeDetails") or "")
        is_shared_mailbox = exchange.get("isSharedMailbox") is True or recipient_type.lower() == "sharedmailbox"
        is_resource_mailbox = exchange.get("isRoomMailbox") is True or exchange.get("isEquipmentMailbox") is True
        has_delegations = exchange.get("delegationsFound") is True
        critical = any(keyword in identity_text for keyword in SERVICE_OR_CRITICAL_KEYWORDS)
        technical = critical or any(keyword in identity_text for keyword in TECHNICAL_KEYWORDS) or is_shared_mailbox or is_resource_mailbox
        synced = user.get("onPremisesSyncEnabled") is True
        has_roles = memberships.get("allDirectoryRolesCount", 0) > 0 or memberships.get("directoryRolesCount", 0) > 0
        is_privileged = security.get("isPrivileged") is True or has_roles
        has_mfa = security.get("hasMfaMethod") is True
        has_license = licenses.get("count", 0) > 0

        sign_activity = user.get("signInActivity") or {}
        last_interactive = parse_graph_datetime(sign_activity.get("lastSignInDateTime"))
        last_non_interactive = parse_graph_datetime(sign_activity.get("lastNonInteractiveSignInDateTime"))
        latest_signal = signals[0] if signals else None
        latest_days = latest_signal.get("daysAgo") if latest_signal else None
        interactive_days = days_since(last_interactive)
        non_interactive_days = days_since(last_non_interactive)

        reasons: list[str] = []
        recommendation: str
        status: str
        score: int
        confidence: str
        risk: str

        if has_mailbox and is_shared_mailbox and latest_days is not None and latest_days <= 90:
            status = "Boite partagee Exchange active"
            score = 88
            confidence = "Haute"
            risk = "Eleve" if has_delegations else "Moyen"
            recommendation = "Conserver. Boite partagee Exchange avec activite recente. Verifier les delegations Full Access / Send As pour identifier les utilisateurs."
            reasons.append(f"Boite partagee Exchange active detectee il y a {latest_days} jour(s).")
        elif has_mailbox and is_shared_mailbox:
            status = "Boite partagee Exchange a confirmer"
            score = 55 if has_delegations else 40
            confidence = "Moyenne"
            risk = "Moyen" if has_delegations else "Faible"
            recommendation = "Verifier les delegations Exchange et le proprietaire avant action. Une boite partagee peut etre utile meme si le compte Entra est desactive ou sans licence."
            reasons.append("Le type Exchange est SharedMailbox.")
        elif has_mailbox and latest_days is not None and latest_days <= 90:
            status = "Boite Exchange active"
            score = 85
            confidence = "Haute"
            risk = "Eleve"
            recommendation = "Conserver. Une boite Exchange avec activite recente a ete detectee."
            reasons.append(f"Activite Exchange recente detectee il y a {latest_days} jour(s).")
        elif exchange_found and not has_mailbox:
            status = "Objet mail Exchange"
            score = 50
            confidence = "Moyenne"
            risk = "Moyen"
            recommendation = "Objet destinataire Exchange trouve sans boite utilisateur. Verifier le type de destinataire avant suppression."
            reasons.append(f"Objet Exchange trouve : {recipient_type or 'type inconnu'}.")
        elif user.get("accountEnabled") is False:
            status = "Compte desactive"
            score = 10
            confidence = "Haute"
            risk = "Faible"
            recommendation = "Compte deja desactive : verifier les licences/boites restantes puis appliquer la procedure de conservation/suppression interne."
            reasons.append("accountEnabled = false dans Microsoft Graph.")
        elif critical:
            status = "Critique infrastructure"
            score = 95
            confidence = "Haute"
            risk = "Eleve"
            recommendation = "Ne pas desactiver. Valider avec l'equipe infrastructure/hybride avant toute action."
            reasons.append("Nom/UPN compatible avec un compte de synchronisation, AD Connect ou infrastructure.")
        elif is_privileged:
            status = "Compte a privileges"
            score = 90
            confidence = "Haute"
            risk = "Eleve"
            recommendation = "Analyser comme compte privilegie. Ne pas desactiver sans validation admin et controle des roles."
            reasons.append("Le compte est membre d'au moins un role d'annuaire direct ou transitif.")
        elif last_non_interactive and non_interactive_days is not None and non_interactive_days <= 90 and (
            interactive_days is None or interactive_days > 90
        ):
            status = "Actif non interactif"
            score = 85
            confidence = "Haute"
            risk = "Eleve" if technical else "Moyen"
            recommendation = "Probable usage applicatif ou token. Documenter le proprietaire et ne pas desactiver sans validation technique."
            reasons.append("Activite non interactive recente sans connexion interactive recente.")
        elif latest_days is not None and latest_days <= 30:
            status = "Actif confirme"
            score = 90
            confidence = "Haute"
            risk = "Eleve"
            recommendation = "Conserver. Une activite Microsoft 365 recente a ete detectee."
            reasons.append(f"Signal Microsoft 365 recent detecte il y a {latest_days} jour(s).")
        elif latest_days is not None and latest_days <= 90:
            status = "Actif recent / a surveiller"
            score = 70
            confidence = "Moyenne"
            risk = "Moyen"
            recommendation = "Conserver pour le moment ou demander confirmation au proprietaire si le compte est atypique."
            reasons.append(f"Dernier signal detecte il y a {latest_days} jour(s).")
        elif latest_days is not None and latest_days <= 180:
            status = "A confirmer"
            score = 45
            confidence = "Moyenne"
            risk = "Moyen"
            recommendation = "Demander validation metier/technique avant toute desactivation."
            reasons.append(f"Dernier signal detecte il y a {latest_days} jour(s).")
        elif technical:
            status = "A confirmer technique"
            score = 35
            confidence = "Moyenne"
            risk = "Eleve"
            recommendation = "Aucun usage M365 recent detecte, mais le nom indique un compte technique. Identifier l'application/proprietaire avant action."
            reasons.append("Indicateurs de compte technique detectes dans le nom, l'UPN ou les alias.")
        elif synced:
            status = "Dormant cote Microsoft 365"
            score = 25
            confidence = "Moyenne"
            risk = "Moyen"
            recommendation = "Aucun usage M365 detecte. Le compte est synchronise depuis l'AD : verifier le proprietaire/RH ou l'AD source avant desactivation."
            reasons.append("Compte encore synchronise depuis l'AD mais sans signal Microsoft 365 exploitable.")
        else:
            status = "Candidat a revue"
            score = 20
            confidence = "Moyenne"
            risk = "Faible" if not has_license else "Moyen"
            recommendation = "Aucun usage Microsoft 365 recent detecte. Verifier le proprietaire avant desactivation."
            if latest_days is None:
                reasons.append("Aucun signal Microsoft 365 exploitable n'a ete trouve.")
            else:
                reasons.append(f"Dernier signal detecte il y a {latest_days} jour(s), au-dela du seuil D180.")

        if technical and not critical and "Indicateurs de compte technique detectes" not in " ".join(reasons):
            reasons.append("Indicateurs de compte technique detectes dans le nom/UPN/alias.")
        if synced:
            reasons.append("Compte synchronise depuis l'AD local vers le tenant.")
        if has_license:
            reasons.append(f"{licenses['count']} licence(s) affectee(s) cote tenant.")
        if has_mailbox:
            reasons.append(f"Boite Exchange detectee : {recipient_type or 'type inconnu'}.")
        if has_delegations:
            reasons.append("Delegations Exchange detectees : Full Access, Send As ou Send on behalf.")
        if is_privileged and not has_mfa:
            reasons.append("Compte privilegie sans methode MFA lisible : verifier MFA / Conditional Access avant toute conclusion.")
        elif has_mfa:
            reasons.append("Au moins une methode MFA/auth forte est lisible via Graph.")
        if report_row is None:
            reasons.append("Aucune ligne trouvee dans le rapport Office 365 Active User Detail.")

        return {
            "status": status,
            "score": score,
            "confidence": confidence,
            "riskLevel": risk,
            "isCriticalCandidate": critical,
            "isTechnicalCandidate": technical,
            "isPrivileged": is_privileged,
            "hasMfaMethod": has_mfa,
            "isSyncedFromOnPrem": synced,
            "exchangeFound": exchange_found,
            "hasExchangeMailbox": has_mailbox,
            "isSharedMailbox": is_shared_mailbox,
            "exchangeRecipientType": recipient_type,
            "exchangeDelegationsFound": has_delegations,
            "latestSignal": latest_signal,
            "latestSignalDaysAgo": latest_days,
            "recommendation": recommendation,
            "recommendedAction": recommendation,
            "usageSummary": self._usage_summary(status, latest_days, technical, synced, has_license, recipient_type if exchange_found else None),
            "reasons": reasons,
            "tenantOnlyWarning": "Cette analyse couvre Microsoft 365 / Entra ID et, si active, Exchange Online. Elle ne prouve pas l'absence d'usage local on-premise.",
        }

    @staticmethod
    def _report_bool(report_row: dict[str, str] | None, column: str) -> bool | None:
        if not report_row or column not in report_row:
            return None
        value = (report_row.get(column) or "").strip().lower()
        if value in {"true", "yes", "1", "vrai", "oui"}:
            return True
        if value in {"false", "no", "0", "faux", "non"}:
            return False
        return None

    @staticmethod
    def _group_importance(display_name: str | None, group: dict[str, Any]) -> str:
        name = (display_name or "").strip().lower()
        if name in LOW_VALUE_GROUP_NAMES:
            return "Standard"
        if any(word in name for word in ["admin", "finance", "daf", "rh", "devops", "vpn", "mfa", "exclusion"]):
            return "Interessant"
        if group.get("securityEnabled") is True:
            return "Securite"
        if "Unified" in (group.get("groupTypes") or []):
            return "M365"
        return "Normal"

    @staticmethod
    def _is_privileged_role(display_name: str | None) -> bool:
        name = (display_name or "").lower()
        return any(keyword in name for keyword in PRIVILEGED_ROLE_KEYWORDS) or "administrator" in name or "admin" in name

    @staticmethod
    def _mfa_recommendation(has_mfa: bool, privileged: bool, methods_readable: bool) -> str:
        if not methods_readable:
            return "MFA inconnu : ajoute/verifie UserAuthenticationMethod.Read.All pour lire les methodes."
        if has_mfa and privileged:
            return "MFA detecte. Verifier quand meme les exclusions Conditional Access pour ce compte privilegie."
        if has_mfa:
            return "MFA ou methode forte detectee."
        if privileged:
            return "Aucune methode MFA detectee : risque eleve pour un compte privilegie."
        return "Aucune methode MFA detectee. A confirmer selon le type de compte et la politique Conditional Access."

    @staticmethod
    def _usage_summary(status: str, latest_days: int | None, technical: bool, synced: bool, has_license: bool, exchange_type: str | None = None) -> str:
        parts = [status]
        if latest_days is None:
            parts.append("aucun signal M365 exploitable")
        else:
            parts.append(f"dernier signal il y a {latest_days} jour(s)")
        if technical:
            parts.append("profil technique probable")
        if synced:
            parts.append("synchronise AD")
        if has_license:
            parts.append("licence affectee")
        if exchange_type:
            parts.append(f"Exchange: {exchange_type}")
        return " - ".join(parts)
