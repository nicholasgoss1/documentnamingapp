"""
Silent GitHub corrections sync using only built-in Python libraries.
Pushes corrections to the corrections-sync branch on GitHub.
"""
import base64
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_REPO = "nicholasgoss1/documentnamingapp"
GITHUB_BRANCH = "corrections-sync"
GITHUB_API = "https://api.github.com"

# Token file locations (checked in order)
_TOKEN_PATHS = [
    "C:/Projects/GitHub sync token.txt",
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "ClaimFileRenamer", "github_token.txt"
    ),
]


class GitHubSync:

    def _find_token(self) -> Optional[str]:
        for path in _TOKEN_PATHS:
            if path and os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        token = f.read().strip()
                    if token:
                        return token
                except Exception:
                    pass
        return None

    def is_available(self) -> bool:
        token = self._find_token()
        if not token:
            return False
        return token.startswith("github_pat_") or token.startswith("ghp_")

    def _api_request(self, method: str, path: str, data: dict = None) -> Optional[dict]:
        token = self._find_token()
        if not token:
            return None
        try:
            url = f"{GITHUB_API}{path}"
            body = json.dumps(data).encode("utf-8") if data else None
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("Authorization", f"token {token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "ClaimsCo-Document-Tools")

            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            logger.debug("GitHub API error %s: %s", e.code, e.reason)
            return None
        except Exception as e:
            logger.debug("GitHub API request failed: %s", e)
            return None

    def _ensure_branch_exists(self) -> bool:
        # Check if branch exists
        result = self._api_request(
            "GET", f"/repos/{GITHUB_REPO}/git/ref/heads/{GITHUB_BRANCH}"
        )
        if result:
            return True

        # Get default branch SHA
        # Try claimsco-documents-manager first, then main
        for branch_name in ["claimsco-documents-manager", "main"]:
            ref = self._api_request(
                "GET", f"/repos/{GITHUB_REPO}/git/ref/heads/{branch_name}"
            )
            if ref:
                sha = ref.get("object", {}).get("sha")
                if sha:
                    create_result = self._api_request(
                        "POST", f"/repos/{GITHUB_REPO}/git/refs",
                        {"ref": f"refs/heads/{GITHUB_BRANCH}", "sha": sha}
                    )
                    return create_result is not None
        return False

    def upload_corrections(self, corrections_path: str) -> bool:
        if not self.is_available():
            return False
        try:
            if not os.path.exists(corrections_path):
                return False

            with open(corrections_path, "r", encoding="utf-8") as f:
                content = f.read()

            computer_name = os.environ.get("COMPUTERNAME", "unknown")
            filename = f"corrections_{computer_name}.json"
            api_path = f"/repos/{GITHUB_REPO}/contents/corrections/{filename}"

            content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

            # Check if file exists to get SHA for update
            existing = self._api_request(
                "GET", f"{api_path}?ref={GITHUB_BRANCH}"
            )

            put_data = {
                "message": f"Sync corrections from {computer_name}",
                "content": content_b64,
                "branch": GITHUB_BRANCH,
            }
            if existing and existing.get("sha"):
                put_data["sha"] = existing["sha"]

            result = self._api_request("PUT", api_path, put_data)
            if result:
                # Update last sync timestamp
                try:
                    from src.services.corrections_store import set_last_sync_time
                    set_last_sync_time()
                except Exception:
                    pass
                return True
            return False
        except Exception as e:
            logger.debug("GitHub upload failed: %s", e)
            return False

    def download_all_corrections(self, dest_folder: str) -> list:
        if not self.is_available():
            return []
        try:
            os.makedirs(dest_folder, exist_ok=True)
            result = self._api_request(
                "GET", f"/repos/{GITHUB_REPO}/contents/corrections?ref={GITHUB_BRANCH}"
            )
            if not result or not isinstance(result, list):
                return []

            downloaded = []
            for item in result:
                name = item.get("name", "")
                if not name.startswith("corrections_") or not name.endswith(".json"):
                    continue
                download_url = item.get("download_url")
                if not download_url:
                    continue
                try:
                    req = urllib.request.Request(download_url)
                    req.add_header("User-Agent", "ClaimsCo-Document-Tools")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                    dest_path = os.path.join(dest_folder, name)
                    with open(dest_path, "wb") as f:
                        f.write(data)
                    downloaded.append(dest_path)
                except Exception as e:
                    logger.debug("Failed to download %s: %s", name, e)
                    continue
            return downloaded
        except Exception as e:
            logger.debug("GitHub download failed: %s", e)
            return []


github_sync = GitHubSync()
