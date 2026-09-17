"""Crawl a SharePoint document library and download supported files."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import unquote, urlparse

import httpx

from ..core.config import (
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_TENANT_ID,
    SHAREPOINT_MAX_FILES,
)
from .file_types import ALLOWED_EXTENSIONS, is_supported_filename

logger = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


@dataclass
class SharePointFile:
    name: str
    relative_path: str
    size: int
    web_url: str
    drive_id: str
    item_id: str


class SharePointError(ValueError):
    """User-facing SharePoint / Graph failure."""


def parse_sharepoint_url(url: str) -> dict:
    """Extract hostname, site path, folder path, and sharing-link flag from a URL."""
    if not url or not url.strip():
        raise SharePointError("Enter a SharePoint site or document library URL.")

    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SharePointError("The SharePoint URL is not valid.")

    hostname = parsed.netloc.lower()
    path = unquote(parsed.path or "/")
    is_share_link = bool(re.search(r"/:([fbu])[:/]", path))

    site_match = re.search(r"/(sites|teams)/([^/]+)", path, re.IGNORECASE)
    site_path = ""
    remainder = path
    if site_match:
        site_path = f"/{site_match.group(1)}/{site_match.group(2)}"
        remainder = path[site_match.end() :]

    remainder = remainder.lstrip("/")
    remainder = re.sub(r"^:([fbu]):[rs]/", "", remainder)
    folder_path = unquote(remainder).strip("/")

    return {
        "hostname": hostname,
        "site_path": site_path,
        "folder_path": folder_path,
        "is_share_link": is_share_link,
        "url": raw,
    }


def _encode_share_id(url: str) -> str:
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    return f"u!{encoded}"


class SharePointClient:
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        self.tenant_id = (tenant_id or GRAPH_TENANT_ID or "").strip()
        self.client_id = (client_id or GRAPH_CLIENT_ID or "").strip()
        self.client_secret = (client_secret or GRAPH_CLIENT_SECRET or "").strip()
        self.access_token = (access_token or "").strip() or None

    async def get_token(self) -> str:
        if self.access_token:
            return self.access_token
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise SharePointError(
                "SharePoint access needs a Microsoft Graph token, or Tenant ID, "
                "Client ID, and Client Secret for an Azure AD app with Sites.Read.All."
            )

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=data)
        if response.status_code >= 400:
            raise SharePointError(
                "Could not sign in to Microsoft Graph. Check the tenant, client ID, "
                "and client secret, and that the app has Sites.Read.All."
            )
        token = response.json().get("access_token")
        if not token:
            raise SharePointError("Microsoft Graph did not return an access token.")
        self.access_token = token
        return token

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = await self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            raise SharePointError(
                "SharePoint rejected the credentials. The token may be expired, "
                "or the Azure AD app lacks Sites.Read.All."
            )
        if response.status_code == 403:
            raise SharePointError(
                "The signed-in app does not have permission to read this library."
            )
        if response.status_code == 404:
            raise SharePointError(
                "The SharePoint site, library, or folder was not found. Check the URL."
            )
        if response.status_code >= 400:
            detail = response.text[:300]
            logger.error("Graph error %s: %s", response.status_code, detail)
            raise SharePointError(
                f"SharePoint request failed ({response.status_code}). {detail}"
            )
        return response

    async def list_supported_files(self, sharepoint_url: str) -> List[SharePointFile]:
        parsed = parse_sharepoint_url(sharepoint_url)
        files: List[SharePointFile] = []
        if parsed["is_share_link"]:
            await self._walk_share_link(parsed["url"], files)
        else:
            await self._walk_library(parsed, files)
        if not files:
            raise SharePointError(
                "No PDF, scanned image, or photo files were found in that library."
            )
        if len(files) > SHAREPOINT_MAX_FILES:
            raise SharePointError(
                f"This library has more than {SHAREPOINT_MAX_FILES} supported files. "
                "Use a more specific folder URL."
            )
        return files

    async def download_file(self, item: SharePointFile) -> bytes:
        url = f"{GRAPH_ROOT}/drives/{item.drive_id}/items/{item.item_id}/content"
        response = await self._request("GET", url)
        return response.content

    async def _walk_share_link(self, url: str, files: List[SharePointFile]) -> None:
        share_id = _encode_share_id(url)
        item_url = f"{GRAPH_ROOT}/shares/{share_id}/driveItem"
        response = await self._request("GET", item_url)
        item = response.json()
        drive_id = (item.get("parentReference") or {}).get("driveId") or item.get("id")
        await self._walk_item(drive_id, item, "", files)

    async def _walk_library(self, parsed: dict, files: List[SharePointFile]) -> None:
        if not parsed["site_path"]:
            raise SharePointError(
                "Use a site or library URL such as "
                "https://contoso.sharepoint.com/sites/HR/Shared Documents."
            )
        site_url = f"{GRAPH_ROOT}/sites/{parsed['hostname']}:{parsed['site_path']}"
        site = (await self._request("GET", site_url)).json()
        site_id = site["id"]
        drives = (await self._request("GET", f"{GRAPH_ROOT}/sites/{site_id}/drives")).json().get("value", [])
        if not drives:
            raise SharePointError("This SharePoint site has no document libraries.")

        folder_path = parsed["folder_path"]
        drive, child_path = self._match_drive(drives, folder_path)
        if child_path:
            encoded = child_path.replace("#", "%23")
            item = (
                await self._request(
                    "GET",
                    f"{GRAPH_ROOT}/drives/{drive['id']}/root:/{encoded}",
                )
            ).json()
        else:
            item = (
                await self._request("GET", f"{GRAPH_ROOT}/drives/{drive['id']}/root")
            ).json()
        await self._walk_item(drive["id"], item, child_path, files)

    def _match_drive(self, drives: list, folder_path: str) -> tuple:
        if not folder_path:
            default = next((d for d in drives if d.get("name") in {"Documents", "Shared Documents"}), drives[0])
            return default, ""

        first, _, rest = folder_path.partition("/")
        aliases = {
            first.lower(),
            first.replace("%20", " ").lower(),
            "documents" if first.lower() == "shared documents" else "",
            "shared documents" if first.lower() == "documents" else "",
        }
        for drive in drives:
            name = (drive.get("name") or "").lower()
            if name in aliases:
                return drive, rest
        # First segment was a folder in the default library
        default = next((d for d in drives if d.get("name") in {"Documents", "Shared Documents"}), drives[0])
        return default, folder_path

    async def _walk_item(
        self,
        drive_id: str,
        item: dict,
        relative_path: str,
        files: List[SharePointFile],
    ) -> None:
        if item.get("file"):
            name = item.get("name") or "file"
            if is_supported_filename(name):
                files.append(
                    SharePointFile(
                        name=name,
                        relative_path=relative_path or name,
                        size=int(item.get("size") or 0),
                        web_url=item.get("webUrl") or "",
                        drive_id=drive_id,
                        item_id=item["id"],
                    )
                )
            return

        children_url = f"{GRAPH_ROOT}/drives/{drive_id}/items/{item['id']}/children"
        while children_url:
            payload = (await self._request("GET", children_url)).json()
            for child in payload.get("value", []):
                child_name = child.get("name") or "item"
                child_path = f"{relative_path}/{child_name}" if relative_path else child_name
                if child.get("folder"):
                    await self._walk_item(drive_id, child, child_path, files)
                elif child.get("file") and is_supported_filename(child_name):
                    files.append(
                        SharePointFile(
                            name=child_name,
                            relative_path=child_path,
                            size=int(child.get("size") or 0),
                            web_url=child.get("webUrl") or "",
                            drive_id=drive_id,
                            item_id=child["id"],
                        )
                    )
                if len(files) > SHAREPOINT_MAX_FILES:
                    return
            children_url = payload.get("@odata.nextLink")
