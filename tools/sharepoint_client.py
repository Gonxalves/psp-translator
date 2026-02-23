"""
SharePoint/OneDrive Sync Client

Downloads and uploads the Glossary Excel file from/to SharePoint
using the sharing URL directly (FedAuth cookie-based authentication).

Only requires:
    SHAREPOINT_SHARING_URL - Sharing URL of the glossary file

No Azure app registration needed. The sharing URL provides both
read (download) and write (upload via REST API) access.
"""

import os
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()


class SharePointClient:
    """
    Sync a single Excel file between local disk and SharePoint/OneDrive
    using the sharing URL for authentication.
    """

    # FedAuth cookies typically last 30-60 min; refresh before expiry
    SESSION_MAX_AGE = 20 * 60  # 20 minutes

    def __init__(self):
        self.sharing_url = os.getenv('SHAREPOINT_SHARING_URL', '')
        self._session: Optional[requests.Session] = None
        self._session_created_at: float = 0
        self._digest: Optional[str] = None
        self._digest_expires_at: float = 0
        self._server_relative_url: Optional[str] = None
        self._base_url: Optional[str] = None
        self._folder_url: Optional[str] = None
        self._file_name: Optional[str] = None

    @property
    def enabled(self) -> bool:
        """Return True if a sharing URL is configured."""
        return bool(self.sharing_url)

    # ------------------------------------------------------------------
    # Authentication via sharing URL
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """
        Get an authenticated session using the download URL.

        Two-step auth to avoid self-locking:
        1. GET sharing URL with allow_redirects=False to extract file GUID
           from the redirect URL (without loading the Doc.aspx viewer)
        2. GET sharing URL + &download=1 to obtain FedAuth cookie
           (download redirect doesn't open the file viewer)

        This prevents the co-authoring lock that Doc.aspx creates,
        which would block subsequent uploads with HTTP 423.
        """
        if self._session is not None:
            age = time.time() - self._session_created_at
            if age < self.SESSION_MAX_AGE and any(c.name == 'FedAuth' for c in self._session.cookies):
                return self._session
            # Session expired or missing cookie - re-authenticate
            self._session = None
            self._digest = None
            self._digest_expires_at = 0

        # Step 1: Extract file GUID from first redirect (no viewer loaded)
        guid = None
        try:
            resp0 = requests.get(self.sharing_url, allow_redirects=False, timeout=10)
            redirect_url = resp0.headers.get('Location', '')
            if redirect_url:
                parsed_redirect = urlparse(redirect_url)
                params = parse_qs(parsed_redirect.query)
                guid = params.get('sourcedoc', [''])[0].strip('{}')

                # Derive base URL from redirect path
                path_before_layouts = parsed_redirect.path.split('/_layouts/')[0]
                self._base_url = f"{parsed_redirect.scheme}://{parsed_redirect.netloc}{path_before_layouts}"
        except Exception:
            pass

        # Fallback: derive base URL from sharing URL
        if not self._base_url:
            parsed = urlparse(self.sharing_url)
            path_parts = parsed.path.split('/')
            for i, part in enumerate(path_parts):
                if part == 'personal' and i + 1 < len(path_parts):
                    self._base_url = f"{parsed.scheme}://{parsed.netloc}/personal/{path_parts[i + 1]}"
                    break

        if not self._base_url:
            raise RuntimeError("Could not derive SharePoint base URL from sharing URL")

        # Step 2: Get FedAuth cookie via download URL (no viewer opened)
        session = requests.Session()
        download_url = self.sharing_url
        if '?' in download_url:
            download_url += '&download=1'
        else:
            download_url += '?download=1'

        resp = session.get(download_url, allow_redirects=True, timeout=20)
        resp.raise_for_status()

        if not any(c.name == 'FedAuth' for c in session.cookies):
            raise RuntimeError("Failed to obtain FedAuth cookie from sharing URL")

        # Step 3: Resolve file path using GUID
        if guid:
            self._resolve_file_path(session, guid)

        self._session = session
        self._session_created_at = time.time()
        return session

    def _invalidate_session(self):
        """Force re-authentication on next call."""
        self._session = None
        self._digest = None
        self._digest_expires_at = 0

    def _resolve_file_path(self, session: requests.Session, guid: str):
        """Resolve file GUID to server-relative URL via GetFileById."""
        if self._folder_url and self._file_name:
            return

        try:
            resp = session.get(
                f"{self._base_url}/_api/web/GetFileById('{guid}')",
                headers={'Accept': 'application/json;odata=verbose'},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json().get('d', {})
                self._server_relative_url = data.get('ServerRelativeUrl', '')
                self._file_name = data.get('Name', '')
                if self._server_relative_url:
                    self._folder_url = '/'.join(self._server_relative_url.split('/')[:-1])
                print(f"[SharePoint] Resolved: {self._file_name} "
                      f"({data.get('Length', '?')} bytes)")
            else:
                print(f"[SharePoint] Warning: GetFileById returned {resp.status_code}")
        except Exception as e:
            print(f"[SharePoint] Warning: Could not resolve file path: {e}")

    def _get_digest(self) -> str:
        """Get a request digest for write operations."""
        if self._digest and time.time() < self._digest_expires_at:
            return self._digest

        session = self._get_session()
        resp = session.post(
            f"{self._base_url}/_api/contextinfo",
            headers={'Accept': 'application/json;odata=verbose'},
            timeout=15,
        )
        resp.raise_for_status()

        info = resp.json()['d']['GetContextWebInformation']
        self._digest = info['FormDigestValue']
        # Digest typically valid for 30 minutes
        self._digest_expires_at = time.time() + info.get('FormDigestTimeoutSeconds', 1800) - 60
        return self._digest

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self, local_path: str) -> bool:
        """
        Download the SharePoint file to a local path.
        Uses the sharing URL with &download=1 (fast, no REST API needed).
        """
        if not self.enabled:
            return False

        try:
            # Direct download via sharing URL (simplest, fastest)
            download_url = self.sharing_url
            if '?' in download_url:
                download_url += '&download=1'
            else:
                download_url += '?download=1'

            resp = requests.get(download_url, allow_redirects=True, timeout=30)
            resp.raise_for_status()

            # Verify it's a valid XLSX
            if resp.content[:4] != b'PK\x03\x04':
                print("[SharePoint] Download returned non-XLSX content, skipping")
                return False

            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(resp.content)

            print(f"[SharePoint] Downloaded glossary ({len(resp.content)} bytes) -> {local_path}")
            return True

        except Exception as e:
            print(f"[SharePoint] Download failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _do_upload(self, local_path: str) -> Tuple[bool, str, int]:
        """Internal upload. Returns (success, message, http_status)."""
        session = self._get_session()
        digest = self._get_digest()

        if not self._folder_url or not self._file_name:
            return False, "Could not resolve file path on SharePoint", 0

        with open(local_path, 'rb') as f:
            data = f.read()

        resp = session.post(
            f"{self._base_url}/_api/web/GetFolderByServerRelativePath("
            f"decodedurl='{self._folder_url}')/Files/Add("
            f"url='{self._file_name}',overwrite=true)",
            headers={
                'Accept': 'application/json;odata=verbose',
                'X-RequestDigest': digest,
            },
            data=data,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            result = resp.json().get('d', {})
            size = result.get('Length', len(data))
            print(f"[SharePoint] Uploaded glossary ({size} bytes)")
            return True, "Synced to SharePoint", resp.status_code

        if resp.status_code == 423:
            return False, "SharePoint file is locked (open elsewhere). Saved locally.", resp.status_code

        error_msg = f"HTTP {resp.status_code}"
        try:
            error_data = resp.json()
            error_msg = error_data.get('error', {}).get('message', {}).get('value', error_msg)
        except Exception:
            pass

        return False, f"SharePoint upload failed: {error_msg}", resp.status_code

    def upload(self, local_path: str) -> Tuple[bool, str]:
        """
        Upload a local file back to SharePoint (overwrite).
        Auto-retries once with a fresh session if auth fails.

        Returns (success, message) tuple.
        """
        if not self.enabled:
            return False, "SharePoint sync not configured"

        try:
            ok, msg, status = self._do_upload(local_path)
            if ok:
                return True, msg

            # Auth expired? Re-authenticate and retry once
            if status in (401, 403):
                print("[SharePoint] Session expired, re-authenticating...")
                self._invalidate_session()
                ok, msg, status = self._do_upload(local_path)
                if ok:
                    return True, msg

            print(f"[SharePoint] Upload failed: {msg}")
            return False, msg

        except Exception as e:
            # Network error or similar - try fresh session once
            try:
                self._invalidate_session()
                ok, msg, status = self._do_upload(local_path)
                if ok:
                    return True, msg
                return False, msg
            except Exception as e2:
                print(f"[SharePoint] Upload failed after retry: {e2}")
                return False, f"SharePoint sync error: {e2}"


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


def upload_glossary(local_path: str) -> Tuple[bool, str]:
    """Convenience: upload local glossary back to SharePoint."""
    return get_sharepoint_client().upload(local_path)
