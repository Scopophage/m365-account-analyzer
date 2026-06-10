from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ACCENT_COLOR = colors.HexColor("#0f4c5c")
HEADER_FILL = colors.HexColor("#dff2f8")
KEY_FILL = colors.HexColor("#eaf6fb")
GRID_COLOR = colors.HexColor("#cfd8dc")
DANGER = colors.HexColor("#8a1f11")
WARNING = colors.HexColor("#8a5a00")
SUCCESS = colors.HexColor("#116b3a")


def _styles():
    styles = getSampleStyleSheet()
    if "Small" not in styles:
        styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10))
    if "Tiny" not in styles:
        styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontSize=6.8, leading=8))
    if "SectionTitle" not in styles:
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading2"],
                fontSize=13,
                leading=16,
                spaceBefore=12,
                spaceAfter=6,
                textColor=ACCENT_COLOR,
            )
        )
    if "Note" not in styles:
        styles.add(ParagraphStyle(name="Note", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#455a64")))
    return styles


def safe(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, list):
        if not value:
            return "-"
        parts = []
        for item in value:
            if isinstance(item, dict):
                label = item.get("displayName") or item.get("userPrincipalName") or item.get("name") or item.get("id") or str(item)
                parts.append(str(label))
            else:
                parts.append(safe(item))
        return ", ".join(parts)
    if isinstance(value, dict):
        label = value.get("displayName") or value.get("userPrincipalName") or value.get("name") or value.get("id")
        return str(label) if label else str(value)
    return str(value)


def p(value: Any, style_name: str = "Small") -> Paragraph:
    return Paragraph(escape(safe(value)).replace("\n", "<br/>"), _styles()[style_name])


def _doc_header(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#607d8b"))
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.55 * cm, f"Page {doc.page}")
    canvas.restoreState()


def kv_table(rows: list[tuple[str, Any]], width: float) -> Table:
    data = [[p(k), p(v)] for k, v in rows]
    if not data:
        data = [[p("Information"), p("-")]]
    table = Table(data, colWidths=[4.8 * cm, width - 4.8 * cm], splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), KEY_FILL),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def list_table(headers: list[str], rows: list[list[Any]], width: float, tiny: bool = False) -> LongTable:
    style_name = "Tiny" if tiny else "Small"
    data = [[Paragraph(f"<b>{escape(str(h))}</b>", _styles()[style_name]) for h in headers]]
    if rows:
        data.extend([[p(cell, style_name) for cell in row] for row in rows])
    else:
        data.append([p("-", style_name)] + [p("", style_name) for _ in headers[1:]])

    col_widths = _col_widths(headers, width)
    table = LongTable(data, colWidths=col_widths, repeatRows=1, splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def _col_widths(headers: list[str], width: float) -> list[float]:
    key = [h.lower() for h in headers]

    def proportional(weights: list[float]) -> list[float]:
        total = sum(weights) or 1
        return [width * (w / total) for w in weights]

    if key == ["signal", "date", "jours", "source"]:
        return proportional([3.0, 2.2, 1.0, 3.8])
    if key == ["nom", "mail", "securite", "type", "importance"] or key == ["nom", "mail", "sécurité", "type", "importance"]:
        return proportional([3.2, 3.0, 1.2, 1.8, 1.5])
    if key == ["date", "application", "ressource", "client", "interactif", "statut", "ip", "lieu"]:
        return proportional([1.8, 2.3, 2.0, 2.0, 1.1, 1.7, 1.6, 1.8])
    if len(headers) == 1:
        return [width]
    if len(headers) == 2:
        return proportional([0.45, 0.55])
    return [width / len(headers)] * len(headers)


def _status_color(status: str | None) -> colors.Color:
    s = (status or "").lower()
    if "actif" in s or "active" in s:
        return SUCCESS
    if "critique" in s or "privileg" in s or "privil" in s:
        return DANGER
    if "confirmer" in s or "revue" in s or "dormant" in s or "technique" in s:
        return WARNING
    return colors.black


def _add_section(story: list[Any], title: str) -> None:
    story.append(Paragraph(title, _styles()["SectionTitle"]))


def _sanitize_filename(name: str) -> str:
    clean = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)
    return clean.strip("._") or "compte"


def pdf_filename_for_account(result: dict[str, Any], fallback: str) -> str:
    identity = result.get("identity") or {}
    raw = identity.get("userPrincipalName") or identity.get("displayName") or fallback or "compte"
    return f"m365-account-{_sanitize_filename(str(raw))}.pdf"


def build_account_pdf(result: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    width = A4[0] - 2.4 * cm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.0 * cm,
        title="M365 Account Analyzer - Fiche compte",
    )
    styles = _styles()
    story: list[Any] = []

    identity = result.get("identity") or {}
    onprem = identity.get("onPremises") or {}
    conclusion = result.get("conclusion") or {}
    security = result.get("security") or {}
    exchange = result.get("exchange") or {}
    ownership = result.get("ownership") or result.get("owner") or {}
    manager = ownership.get("manager") or {}
    licenses = result.get("licenses") or {}
    activity = result.get("m365Activity") or {}
    sign = result.get("signInActivity") or {}
    memberships = result.get("memberships") or {}

    title = identity.get("displayName") or identity.get("userPrincipalName") or result.get("searchedIdentifier") or "Compte"
    story.append(Paragraph(f"M365 Account Analyzer - {escape(safe(title))}", styles["Title"]))
    subtitle = identity.get("userPrincipalName") or result.get("searchedIdentifier") or ""
    story.append(Paragraph(escape(safe(subtitle)), styles["Small"]))
    story.append(Paragraph(f"Analyse generee le {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Note"]))
    story.append(Spacer(1, 0.25 * cm))

    status = conclusion.get("status")
    score = conclusion.get("score")
    risk = conclusion.get("riskLevel") or conclusion.get("risk")
    confidence = conclusion.get("confidence")
    color_hex = '#116b3a' if _status_color(status) == SUCCESS else ('#8a1f11' if _status_color(status) == DANGER else ('#8a5a00' if _status_color(status) == WARNING else '#000000'))
    story.append(Paragraph(f"<font color='{color_hex}'><b>{escape(safe(status))}</b></font> - Score {escape(safe(score))} - Risque {escape(safe(risk))} - Confiance {escape(safe(confidence))}", styles["Normal"]))

    _add_section(story, "Conclusion")
    story.append(
        kv_table(
            [
                ("Statut", status),
                ("Score", score),
                ("Risque", risk),
                ("Confiance", confidence),
                ("Resume", conclusion.get("usageSummary")),
                ("Technique probable", conclusion.get("isTechnicalCandidate")),
                ("Critique potentiel", conclusion.get("isCriticalCandidate")),
                ("Privilegie", conclusion.get("isPrivileged")),
                ("MFA detecte", conclusion.get("hasMfaMethod")),
                ("Dernier signal", (conclusion.get("latestSignal") or {}).get("date")),
                ("Jours depuis dernier signal", conclusion.get("latestSignalDaysAgo")),
                ("Recommandation", conclusion.get("recommendation")),
                ("Raisons", conclusion.get("reasons") or []),
            ],
            width,
        )
    )

    _add_section(story, "Identite")
    story.append(
        kv_table(
            [
                ("Nom", identity.get("displayName")),
                ("UPN", identity.get("userPrincipalName")),
                ("Mail", identity.get("mail")),
                ("Compte active", identity.get("accountEnabled")),
                ("Type", identity.get("userType")),
                ("Cree le", identity.get("createdDateTime")),
                ("Mot de passe change", identity.get("lastPasswordChangeDateTime")),
                ("Service", identity.get("department")),
                ("Titre", identity.get("jobTitle")),
                ("Societe", identity.get("companyName")),
                ("Bureau", identity.get("officeLocation")),
                ("Employee type", identity.get("employeeType")),
                ("Employee ID", identity.get("employeeId")),
                ("Id objet", identity.get("id")),
            ],
            width,
        )
    )

    _add_section(story, "Synchronisation on-premise")
    story.append(
        kv_table(
            [
                ("Synchronise AD", onprem.get("syncEnabled")),
                ("SamAccountName", onprem.get("samAccountName")),
                ("Derniere synchro", onprem.get("lastSyncDateTime")),
                ("Domaine", onprem.get("domainName")),
                ("UPN on-prem", onprem.get("userPrincipalName")),
                ("DN", onprem.get("distinguishedName")),
            ],
            width,
        )
    )

    _add_section(story, "Microsoft 365 / sign-ins")
    story.append(
        kv_table(
            [
                ("Derniere connexion reussie", sign.get("lastSuccessfulSignInDateTime")),
                ("Derniere interactive", sign.get("lastSignInDateTime")),
                ("Derniere non interactive", sign.get("lastNonInteractiveSignInDateTime")),
                ("Rapport M365", activity.get("reportStatus")),
                ("Rapport actualise", activity.get("reportRefreshDate")),
                ("Exchange activity", activity.get("exchangeLastActivityDate")),
                ("OneDrive", activity.get("oneDriveLastActivityDate")),
                ("SharePoint", activity.get("sharePointLastActivityDate")),
                ("Teams", activity.get("teamsLastActivityDate")),
                ("Yammer", activity.get("yammerLastActivityDate")),
            ],
            width,
        )
    )

    _add_section(story, "Exchange Online")
    story.append(
        kv_table(
            [
                ("Exchange active", exchange.get("enabled")),
                ("Objet trouve", exchange.get("found") or exchange.get("recipientFound")),
                ("Disponible", exchange.get("available")),
                ("Type destinataire", exchange.get("recipientTypeDetails")),
                ("Boite aux lettres", exchange.get("hasMailbox")),
                ("Boite partagee", exchange.get("isSharedMailbox")),
                ("Salle", exchange.get("isRoomMailbox")),
                ("Equipement", exchange.get("isEquipmentMailbox")),
                ("SMTP principal", exchange.get("primarySmtpAddress")),
                ("Masque GAL", exchange.get("hiddenFromAddressLists")),
                ("Derniere action utilisateur", exchange.get("lastUserActionTime")),
                ("Dernier logon boite", exchange.get("lastLogonTime")),
                ("Derniere interaction", exchange.get("lastInteractionTime")),
                ("Taille", exchange.get("totalItemSize")),
                ("Elements", exchange.get("itemCount")),
                ("Full Access", exchange.get("fullAccessCount")),
                ("Send As", exchange.get("sendAsCount")),
                ("Send on behalf", exchange.get("sendOnBehalfCount")),
                ("Delegations", exchange.get("delegationsFound")),
                ("Erreur", exchange.get("error")),
            ],
            width,
        )
    )

    _add_section(story, "MFA / privileges")
    story.append(
        kv_table(
            [
                ("MFA detecte", security.get("hasMfaMethod")),
                ("Methodes lisibles", security.get("methodsReadable")),
                ("Nombre methodes", security.get("methodsCount")),
                ("Compte privilegie", security.get("isPrivileged")),
                ("Roles privilegies", security.get("privilegedRoles") or []),
                ("Recommandation MFA", security.get("mfaRecommendation")),
            ],
            width,
        )
    )

    _add_section(story, "Proprietaire probable")
    story.append(
        kv_table(
            [
                ("Manager", manager.get("displayName")),
                ("Manager UPN", manager.get("userPrincipalName")),
                ("Service", ownership.get("department")),
                ("Societe", ownership.get("companyName")),
                ("Bureau", ownership.get("officeLocation")),
                ("Proprietaire probable", ownership.get("probableOwner")),
                ("Objets possedes", ownership.get("ownedObjectsCount")),
            ],
            width,
        )
    )

    story.append(PageBreak())

    _add_section(story, "Licences")
    license_rows = []
    for item in licenses.get("items") or []:
        license_rows.append([item.get("skuPartNumber") or item.get("skuId"), item.get("skuId"), item.get("disabledPlans") or []])
    story.append(kv_table([("Nombre", licenses.get("count")), ("Exchange", licenses.get("hasExchangeLicense")), ("OneDrive", licenses.get("hasOneDriveLicense")), ("SharePoint", licenses.get("hasSharePointLicense")), ("Teams", licenses.get("hasTeamsLicense")), ("Produits rapport", licenses.get("assignedProductsFromReport") or [])], width))
    story.append(Spacer(1, 0.15 * cm))
    story.append(list_table(["SKU", "ID", "Plans desactives"], license_rows, width, tiny=True))

    _add_section(story, "Alias / proxyAddresses")
    aliases = identity.get("proxyAddresses") or exchange.get("aliases") or []
    story.append(list_table(["Alias"], [[a] for a in aliases], width, tiny=True))

    _add_section(story, "Methodes MFA / authentification")
    story.append(list_table(["Methode", "Type Graph"], [[m.get("display") or m.get("label"), m.get("type")] for m in security.get("methods") or []], width))

    _add_section(story, "Signaux exploites")
    story.append(list_table(["Signal", "Date", "Jours", "Source"], [[s.get("name"), s.get("date"), s.get("daysAgo"), s.get("source")] for s in result.get("signals") or []], width))

    _add_section(story, "Derniers sign-ins disponibles")
    story.append(
        list_table(
            ["Date", "Application", "Ressource", "Client", "Interactif", "Statut", "IP", "Lieu"],
            [
                [
                    s.get("createdDateTime"),
                    s.get("appDisplayName"),
                    s.get("resourceDisplayName"),
                    s.get("clientAppUsed"),
                    s.get("isInteractive"),
                    "Succes" if s.get("statusCode") == 0 else (s.get("statusFailureReason") or s.get("statusCode")),
                    s.get("ipAddress"),
                    ", ".join([x for x in [s.get("city"), s.get("countryOrRegion")] if x]),
                ]
                for s in result.get("recentSignIns") or []
            ],
            width,
            tiny=True,
        )
    )

    _add_section(story, "Groupes directs")
    story.append(
        list_table(
            ["Nom", "Mail", "Securite", "Type", "Importance"],
            [[g.get("displayName"), g.get("mail"), g.get("securityEnabled"), ", ".join(g.get("groupTypes") or []) or g.get("type"), g.get("importance")] for g in memberships.get("groups") or []],
            width,
            tiny=True,
        )
    )

    _add_section(story, "Roles d'annuaire")
    role_rows = [[r.get("displayName"), "Direct", r.get("id")] for r in memberships.get("directoryRoles") or []]
    role_rows += [[r.get("displayName"), "Transitif", r.get("id")] for r in memberships.get("transitiveDirectoryRoles") or []]
    story.append(list_table(["Role", "Portee", "Id"], role_rows, width, tiny=True))

    _add_section(story, "Delegations Exchange")
    story.append(Paragraph("Full Access", styles["Heading3"]))
    story.append(list_table(["Utilisateur", "Droits"], [[x.get("user"), x.get("accessRights") or []] for x in exchange.get("fullAccess") or []], width))
    story.append(Paragraph("Send As", styles["Heading3"]))
    story.append(list_table(["Utilisateur", "Droits"], [[x.get("trustee"), x.get("accessRights") or []] for x in exchange.get("sendAs") or []], width))
    story.append(Paragraph("Send on behalf", styles["Heading3"]))
    story.append(list_table(["Utilisateur"], [[x] for x in exchange.get("sendOnBehalfTo") or []], width))

    warnings = result.get("warnings") or []
    if warnings:
        _add_section(story, "Avertissements")
        story.append(list_table(["Avertissement"], [[w] for w in warnings], width))

    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("Note de perimetre : cette analyse couvre Microsoft 365 / Entra ID et, si active, Exchange Online. Elle ne prouve pas l'absence d'usage local on-premise.", styles["Note"]))

    doc.build(story, onFirstPage=_doc_header, onLaterPages=_doc_header)
    buffer.seek(0)
    return buffer.getvalue()


def _flatten_batch_item(item: dict[str, Any]) -> dict[str, Any]:
    if not item.get("ok"):
        return {
            "identifier": item.get("identifier"),
            "ok": "non",
            "nom": "",
            "upn": "",
            "statut": "Erreur analyse",
            "score": 0,
            "risque": "Inconnu",
            "confiance": "Faible",
            "technique": "",
            "privilegie": "",
            "mfa": "",
            "exchange_type": "",
            "shared": "",
            "jours": "",
            "recommandation": item.get("error") or "Erreur inconnue",
        }
    result = item.get("result") or item
    identity = result.get("identity") or {}
    conclusion = result.get("conclusion") or {}
    security = result.get("security") or {}
    exchange = result.get("exchange") or {}
    latest = conclusion.get("latestSignal") or {}
    return {
        "identifier": item.get("identifier") or result.get("searchedIdentifier"),
        "ok": "oui",
        "nom": identity.get("displayName"),
        "upn": identity.get("userPrincipalName"),
        "statut": conclusion.get("status"),
        "score": conclusion.get("score"),
        "risque": conclusion.get("riskLevel"),
        "confiance": conclusion.get("confidence"),
        "technique": conclusion.get("isTechnicalCandidate"),
        "privilegie": conclusion.get("isPrivileged"),
        "mfa": security.get("hasMfaMethod") or conclusion.get("hasMfaMethod"),
        "exchange_type": exchange.get("recipientTypeDetails"),
        "shared": exchange.get("isSharedMailbox"),
        "jours": conclusion.get("latestSignalDaysAgo"),
        "dernier_signal": latest.get("date"),
        "recommandation": conclusion.get("recommendation"),
    }


def build_batch_pdf(results: list[dict[str, Any]], summary: dict[str, Any] | None = None) -> bytes:
    buffer = BytesIO()
    page_size = landscape(A4)
    width = page_size[0] - 2.0 * cm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=1.0 * cm,
        leftMargin=1.0 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title="M365 Account Analyzer - Analyse en lot",
    )
    styles = _styles()
    story: list[Any] = []

    rows = [_flatten_batch_item(item) for item in results]
    story.append(Paragraph("M365 Account Analyzer - Analyse en lot", styles["Title"]))
    story.append(Paragraph(f"Analyse generee le {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Note"]))
    story.append(Spacer(1, 0.3 * cm))

    if summary:
        _add_section(story, "Resume global")
        summary_rows = [(str(k), v) for k, v in summary.items()]
        story.append(kv_table(summary_rows, width))
        story.append(Spacer(1, 0.25 * cm))

    _add_section(story, "Resultats")
    data_rows = [
        [
            r.get("identifier"),
            r.get("ok"),
            r.get("nom"),
            r.get("upn"),
            r.get("statut"),
            r.get("score"),
            r.get("risque"),
            r.get("confiance"),
            r.get("technique"),
            r.get("privilegie"),
            r.get("mfa"),
            r.get("exchange_type"),
            r.get("shared"),
            r.get("jours"),
            r.get("recommandation"),
        ]
        for r in rows
    ]
    headers = ["Recherche", "OK", "Nom", "UPN", "Statut", "Score", "Risque", "Confiance", "Technique", "Priv.", "MFA", "Exchange", "Partagee", "Jours", "Recommandation"]
    col_widths = [2.2 * cm, 0.8 * cm, 2.6 * cm, 3.3 * cm, 2.8 * cm, 0.9 * cm, 1.2 * cm, 1.3 * cm, 1.2 * cm, 1.0 * cm, 0.9 * cm, 1.7 * cm, 1.0 * cm, 0.9 * cm, 5.9 * cm]
    table = LongTable([[Paragraph(f"<b>{escape(h)}</b>", styles["Tiny"]) for h in headers]] + [[p(cell, "Tiny") for cell in row] for row in data_rows], colWidths=col_widths, repeatRows=1, splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("Note de perimetre : le PDF est une synthese. Pour filtrer et retraiter les donnees, utilise aussi l'export Excel.", styles["Note"]))

    doc.build(story, onFirstPage=_doc_header, onLaterPages=_doc_header)
    buffer.seek(0)
    return buffer.getvalue()
