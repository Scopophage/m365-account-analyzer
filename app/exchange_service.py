from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import BASE_DIR, settings


class ExchangeOnlineService:
    """Lecture live Exchange Online via le module PowerShell ExchangeOnlineManagement.

    Microsoft Graph ne fournit pas proprement RecipientTypeDetails, les statistiques
    de boite, FullAccess, SendAs et SendOnBehalf. Cette classe interroge donc
    Exchange Online PowerShell en backend local, avec authentification app-only
    par certificat de preference.
    """

    def __init__(self) -> None:
        self.script_path = BASE_DIR / "tools" / "exchange_lookup.ps1"

    def lookup_for_user(self, identifier: str, user: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        base = self._disabled_result()

        if not settings.enable_exchange_online:
            return base, warnings

        missing = settings.exchange_missing_configuration()
        if missing:
            return {
                "enabled": True,
                "available": False,
                "configured": False,
                "found": False,
                "error": "Configuration Exchange Online incomplete : " + ", ".join(missing),
            }, [
                "Exchange Online active mais configuration incomplete : "
                + ", ".join(missing)
                + ". Renseigne EXCHANGE_ORGANIZATION et l'authentification Exchange dans .env."
            ]

        candidates = self._build_candidates(identifier, user)
        if not candidates:
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": "Aucun identifiant Exchange exploitable.",
            }, ["Exchange Online : aucun UPN/mail/alias exploitable pour la recherche."]

        cache_key = self._cache_key(candidates)
        cache_path = settings.cache_dir / f"exchange_lookup_{cache_key}.json"
        ttl_seconds = max(settings.exchange_cache_minutes, 0) * 60
        if ttl_seconds > 0 and cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl_seconds:
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                cached["fromCache"] = True
                return cached, warnings
            except (OSError, ValueError):
                pass

        payload = {
            "mode": "lookup",
            "identifiers": candidates,
            "organization": settings.exchange_organization,
            "authMode": settings.exchange_auth_mode,
            "appId": settings.exchange_app_id,
            "certificateThumbprint": settings.exchange_certificate_thumbprint,
            "adminUpn": settings.exchange_admin_upn,
            "includePermissions": settings.exchange_include_permissions,
        }

        result, run_warnings = self._run_exchange_script(payload)
        warnings.extend(run_warnings)

        if ttl_seconds > 0 and result.get("available") is True:
            try:
                cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                warnings.append("Exchange Online : impossible d'ecrire le cache local.")

        return result, warnings

    def diagnostic(self) -> tuple[dict[str, Any], list[str]]:
        if not settings.enable_exchange_online:
            return {"enabled": False, "ok": None, "detail": "ENABLE_EXCHANGE_ONLINE=false"}, []
        missing = settings.exchange_missing_configuration()
        if missing:
            return {
                "enabled": True,
                "ok": False,
                "detail": "Configuration Exchange incomplete : " + ", ".join(missing),
            }, []
        payload = {
            "mode": "diagnostic",
            "organization": settings.exchange_organization,
            "authMode": settings.exchange_auth_mode,
            "appId": settings.exchange_app_id,
            "certificateThumbprint": settings.exchange_certificate_thumbprint,
            "adminUpn": settings.exchange_admin_upn,
            "includePermissions": False,
        }
        result, warnings = self._run_exchange_script(payload)
        return result, warnings

    @staticmethod
    def _disabled_result() -> dict[str, Any]:
        return {
            "enabled": False,
            "available": False,
            "configured": False,
            "found": False,
            "hasMailbox": False,
            "recipientFound": False,
            "isSharedMailbox": False,
            "isRoomMailbox": False,
            "isEquipmentMailbox": False,
            "delegationsFound": False,
            "source": "Exchange Online disabled",
        }

    @staticmethod
    def _build_candidates(identifier: str, user: dict[str, Any]) -> list[str]:
        raw: list[str] = [
            identifier,
            user.get("userPrincipalName") or "",
            user.get("mail") or "",
            user.get("onPremisesUserPrincipalName") or "",
        ]
        for alias in user.get("proxyAddresses") or []:
            value = str(alias)
            if ":" in value:
                value = value.split(":", 1)[1]
            raw.append(value)

        seen: set[str] = set()
        result: list[str] = []
        for value in raw:
            cleaned = str(value or "").strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result[:25]

    @staticmethod
    def _cache_key(candidates: list[str]) -> str:
        joined = "\n".join([c.lower() for c in candidates])
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]

    def _run_exchange_script(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        if not self.script_path.exists():
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": f"Script Exchange introuvable : {self.script_path}",
            }, [f"Script Exchange introuvable : {self.script_path}"]

        ps_exe = self._find_powershell()
        if not ps_exe:
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": "PowerShell introuvable pour lancer ExchangeOnlineManagement.",
            }, ["Exchange Online : powershell.exe/pwsh introuvable."]

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tmp:
            json.dump(payload, tmp, ensure_ascii=False)
            tmp_path = Path(tmp.name)

        try:
            cmd = [
                ps_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.script_path),
                "-InputJsonPath",
                str(tmp_path),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(settings.exchange_timeout_seconds, 30),
            )
        except subprocess.TimeoutExpired:
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": f"Timeout Exchange Online apres {settings.exchange_timeout_seconds} secondes.",
            }, ["Exchange Online : timeout pendant l'appel PowerShell."]
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            message = stderr or stdout or f"Code retour PowerShell {proc.returncode}"
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": message[:2000],
            }, ["Exchange Online : erreur PowerShell. " + message[:500]]

        try:
            data = json.loads(stdout)
            data.setdefault("enabled", True)
            data.setdefault("available", True)
            data.setdefault("configured", True)
            if stderr:
                warnings.append("Exchange Online stderr : " + stderr[:500])
            return data, warnings
        except ValueError:
            return {
                "enabled": True,
                "available": False,
                "configured": True,
                "found": False,
                "error": "Reponse Exchange non JSON : " + stdout[:1000],
            }, ["Exchange Online : reponse PowerShell non JSON."]

    @staticmethod
    def _find_powershell() -> str | None:
        configured = settings.exchange_powershell_path.strip()
        if configured:
            return configured
        for name in ["pwsh", "powershell.exe", "powershell"]:
            found = shutil.which(name)
            if found:
                return found
        return None
