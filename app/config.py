from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    tenant_id: str
    client_id: str
    client_secret: str
    graph_period: str = "D180"
    report_cache_hours: int = 12
    enable_reports: bool = True
    enable_exchange_online: bool = False
    exchange_auth_mode: str = "app_certificate"
    exchange_organization: str = ""
    exchange_app_id: str = ""
    exchange_certificate_thumbprint: str = ""
    exchange_admin_upn: str = ""
    exchange_include_permissions: bool = True
    exchange_cache_minutes: int = 30
    exchange_timeout_seconds: int = 120
    exchange_powershell_path: str = ""
    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    cache_dir: Path = BASE_DIR / "cache"

    @staticmethod
    def load() -> "Settings":
        period = os.getenv("GRAPH_PERIOD", "D180").strip().upper()
        if period not in {"D7", "D30", "D90", "D180"}:
            period = "D180"

        try:
            cache_hours = int(os.getenv("REPORT_CACHE_HOURS", "12"))
        except ValueError:
            cache_hours = 12

        try:
            exchange_cache_minutes = int(os.getenv("EXCHANGE_CACHE_MINUTES", "30"))
        except ValueError:
            exchange_cache_minutes = 30

        try:
            exchange_timeout_seconds = int(os.getenv("EXCHANGE_TIMEOUT_SECONDS", "120"))
        except ValueError:
            exchange_timeout_seconds = 120

        auth_mode = os.getenv("EXCHANGE_AUTH_MODE", "app_certificate").strip().lower()
        if auth_mode not in {"app_certificate", "interactive"}:
            auth_mode = "app_certificate"

        return Settings(
            tenant_id=os.getenv("TENANT_ID", "").strip(),
            client_id=os.getenv("CLIENT_ID", "").strip(),
            client_secret=os.getenv("CLIENT_SECRET", "").strip(),
            graph_period=period,
            report_cache_hours=cache_hours,
            enable_reports=_bool_env("ENABLE_REPORTS", True),
            enable_exchange_online=_bool_env("ENABLE_EXCHANGE_ONLINE", False),
            exchange_auth_mode=auth_mode,
            exchange_organization=os.getenv("EXCHANGE_ORGANIZATION", "").strip(),
            exchange_app_id=os.getenv("EXCHANGE_APP_ID", "").strip(),
            exchange_certificate_thumbprint=os.getenv("EXCHANGE_CERTIFICATE_THUMBPRINT", "").strip(),
            exchange_admin_upn=os.getenv("EXCHANGE_ADMIN_UPN", "").strip(),
            exchange_include_permissions=_bool_env("EXCHANGE_INCLUDE_PERMISSIONS", True),
            exchange_cache_minutes=exchange_cache_minutes,
            exchange_timeout_seconds=exchange_timeout_seconds,
            exchange_powershell_path=os.getenv("EXCHANGE_POWERSHELL_PATH", "").strip(),
        )

    def validate(self) -> list[str]:
        missing = []
        if not self.tenant_id:
            missing.append("TENANT_ID")
        if not self.client_id:
            missing.append("CLIENT_ID")
        if not self.client_secret:
            missing.append("CLIENT_SECRET")
        return missing

    def exchange_missing_configuration(self) -> list[str]:
        if not self.enable_exchange_online:
            return []
        missing = []
        if not self.exchange_organization:
            missing.append("EXCHANGE_ORGANIZATION")
        if self.exchange_auth_mode == "app_certificate":
            if not self.exchange_app_id:
                missing.append("EXCHANGE_APP_ID")
            if not self.exchange_certificate_thumbprint:
                missing.append("EXCHANGE_CERTIFICATE_THUMBPRINT")
        elif self.exchange_auth_mode == "interactive":
            if not self.exchange_admin_upn:
                missing.append("EXCHANGE_ADMIN_UPN")
        return missing


settings = Settings.load()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
