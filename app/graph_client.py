from __future__ import annotations

import time
from typing import Any, Iterable
from urllib.parse import quote

import msal
import requests

from .config import settings


class GraphApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, details: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class GraphClient:
    def __init__(self) -> None:
        missing = settings.validate()
        if missing:
            raise GraphApiError(
                "Configuration .env incomplète : " + ", ".join(missing),
                status_code=None,
            )

        authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.client_id,
            authority=authority,
            client_credential=settings.client_secret,
        )
        self._session = requests.Session()
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @staticmethod
    def quote_id(value: str) -> str:
        return quote(value, safe="")

    @staticmethod
    def escape_odata_string(value: str) -> str:
        return value.replace("'", "''")

    def _token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 120:
            return self._access_token

        result = self._app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise GraphApiError(
                "Impossible d'obtenir un jeton Microsoft Graph. Vérifie le tenant, le client ID, le secret et le consentement admin.",
                details=result,
            )
        self._access_token = result["access_token"]
        expires_in = int(result.get("expires_in", 3599))
        self._token_expires_at = now + expires_in
        return self._access_token

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{settings.graph_base_url}/{path_or_url.lstrip('/')}"

    def get(
        self,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> dict[str, Any]:
        response = self._session.get(
            self._url(path_or_url),
            params=params,
            headers=self._headers(headers),
            timeout=60,
            allow_redirects=allow_redirects,
        )
        if response.status_code >= 400:
            raise self._error_from_response(response)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GraphApiError("Réponse Graph non JSON inattendue.", response.status_code, response.text[:500]) from exc

    def get_all(
        self,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = path_or_url
        next_params = params
        pages = 0
        while next_url and pages < max_pages:
            data = self.get(next_url, params=next_params, headers=headers)
            items.extend(data.get("value", []))
            next_url = data.get("@odata.nextLink")
            next_params = None
            pages += 1
        return items

    def download_report_csv(self, path: str) -> str:
        # Les APIs reports renvoient normalement un 302 vers une URL pré-authentifiée courte durée.
        response = self._session.get(
            self._url(path),
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=60,
            allow_redirects=False,
        )

        if response.status_code == 302:
            location = response.headers.get("Location")
            if not location:
                raise GraphApiError("Graph Reports a renvoyé un 302 sans en-tête Location.", response.status_code)
            report_response = self._session.get(location, timeout=120)
            if report_response.status_code >= 400:
                raise self._error_from_response(report_response)
            return report_response.text

        if response.status_code >= 400:
            raise self._error_from_response(response)

        return response.text

    def _error_from_response(self, response: requests.Response) -> GraphApiError:
        try:
            body = response.json()
            graph_message = body.get("error", {}).get("message") or str(body)
        except ValueError:
            body = response.text[:1000]
            graph_message = response.text[:300]
        return GraphApiError(
            f"Erreur Microsoft Graph {response.status_code}: {graph_message}",
            status_code=response.status_code,
            details=body,
        )
