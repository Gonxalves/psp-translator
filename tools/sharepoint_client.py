"""
SharePoint/OneDrive Sync Client

Downloads and uploads the Glossary Excel file from/to SharePoint
using Microsoft Graph API with application (client credentials) authentication.

Required environment variables:
    AZURE_TENANT_ID     - Azure AD tenant ID
    AZURE_CLIENT_ID     - Registered app client ID
    AZURE_CLIENT_SECRET - App client secret
    SHAREPOINT_SHARING_URL - Sharing URL of the glossary file

If any of these are missing, SharePoint sync is silently disabled
and the app falls back to local-only Excel files.
"""

import os
import base64
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class SharePointClient:
    """
    Sync a single Excel file between local disk and SharePoint/OneDrive
    via the Microsoft Graph API.
    """

    def __init__(self):
        self.tenant_id = os.getenv('AZURE_TENANT_ID', '')
        self.client_id = os.getenv('AZURE_CLIENT_ID', '')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET', '')
        self.sharing_url = os.getenv('SHAREPOINT_SHARING_URL', '')

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._drive_id: Optional[str] = None
        self._item_id: Optional[str] = None

    @property
    def enabled(self) -> bool:
        """Return True if all required env vars are configured."""
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.sharing_url
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Acquire or reuse a Graph API access token (client credentials flow)."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        try:
            from msal import ConfidentialClientApplication
        except ImportError:
            raise ImportError(
                "msal package is required for SharePoint sync. "
                "Install it with: pip install msal"
            )

        app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "unknown"))
            raise RuntimeError(f"Failed to acquire Graph API token: {error}")

        self._access_token = result["access_token"]
        self._token_expires_at = time.time() + result.get("expires_in", 3600)
        return self._access_token

    # ------------------------------------------------------------------
    # Sharing-link resolution
    # ------------------------------------------------------------------

    def _encode_sharing_url(self, url: str) -> str:
        """Encode a sharing URL for the /shares endpoint."""
        encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
        return f"u!{encoded}"

    def _resolve_sharing_link(self):
        """Resolve the sharing URL to get drive_id and item_id."""
        token = self._get_token()
        encoded = self._encode_sharing_url(self.sharing_url)

        resp = requests.get(
            f"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()

        item = resp.json()
        self._drive_id = item['parentReference']['driveId']
        self._item_id = item['id']

        print(f"[SharePoint] Resolved file: {item.get('name', '?')} "
              f"(size: {item.get('size', '?')} bytes)")

    def _ensure_resolved(self):
        """Ensure drive_id and item_id are available."""
        if not self._drive_id or not self._item_id:
            self._resolve_sharing_link()

    # ------------------------------------------------------------------
    # Download / Upload
    # ------------------------------------------------------------------

    def download(self, local_path: str) -> bool:
        """
        Download the SharePoint file to a local path.

        Returns True on success, False on failure (logged but not raised).
        """
        if not self.enabled:
            return False

        try:
            self._ensure_resolved()
            token = self._get_token()

            resp = requests.get(
                f"https://graph.microsoft.com/v1.0/drives/{self._drive_id}"
                f"/items/{self._item_id}/content",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            resp.raise_for_status()

            # Ensure parent directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, 'wb') as f:
                f.write(resp.content)

            print(f"[SharePoint] Downloaded glossary ({len(resp.content)} bytes) -> {local_path}")
            return True

        except Exception as e:
            print(f"[SharePoint] Download failed: {e}")
            return False

    def upload(self, local_path: str) -> bool:
        """
        Upload a local file back to SharePoint (overwrite).

        Returns True on success, False on failure (logged but not raised).
        """
        if not self.enabled:
            return False

        try:
            self._ensure_resolved()
            token = self._get_token()

            with open(local_path, 'rb') as f:
                data = f.read()

            resp = requests.put(
                f"https://graph.microsoft.com/v1.0/drives/{self._drive_id}"
                f"/items/{self._item_id}/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                },
                data=data,
                timeout=60,
            )
            resp.raise_for_status()

            print(f"[SharePoint] Uploaded glossary ({len(data)} bytes) from {local_path}")
            return True

        except Exception as e:
            print(f"[SharePoint] Upload failed: {e}")
            return False


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_instance: Optional[SharePointClient] = None


def get_sharepoint_client() -> SharePointClient:
    """Get or create the singleton SharePoint client."""
    global _instance
    if _instance is None:
        _instance = SharePointClient()
    return _instance


def is_sharepoint_enabled() -> bool:
    """Check if SharePoint sync is configured."""
    return get_sharepoint_client().enabled


def download_glossary(local_path: str) -> bool:
    """Convenience: download glossary from SharePoint to local path."""
    return get_sharepoint_client().download(local_path)


def upload_glossary(local_path: str) -> bool:
    """Convenience: upload local glossary back to SharePoint."""
    return get_sharepoint_client().upload(local_path)
