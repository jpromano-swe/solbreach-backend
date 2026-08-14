from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from asyncio import to_thread
from dataclasses import dataclass


class GitHubPullRequestError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PullRequestDraft:
    branch: str
    file_path: str
    title: str
    body: str
    content: str


@dataclass(frozen=True, slots=True)
class PullRequestResult:
    url: str
    number: int | None


class GitHubBreachRoomClient:
    def __init__(
        self,
        *,
        repo: str,
        base_branch: str,
        token: str | None,
    ) -> None:
        self._repo = repo
        self._base_branch = base_branch
        self._token = token
        self._base_url = "https://api.github.com"

    async def create_submission_pr(self, draft: PullRequestDraft) -> PullRequestResult:
        if not self._token:
            raise GitHubPullRequestError(
                "BREACH_ROOMS_GITHUB_TOKEN or GITHUB_TOKEN is not configured"
            )
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base_sha = await self._base_branch_sha(headers)
        await self._create_branch(headers, draft.branch, base_sha)
        await self._create_file(headers, draft)
        return await self._create_pull_request(headers, draft)

    async def _base_branch_sha(self, headers: dict[str, str]) -> str:
        data = await _request_json(
            "GET",
            f"{self._base_url}/repos/{self._repo}/git/ref/heads/{self._base_branch}",
            headers=headers,
        )
        return str(data["object"]["sha"])

    async def _create_branch(self, headers: dict[str, str], branch: str, sha: str) -> None:
        try:
            await _request_json(
                "POST",
                f"{self._base_url}/repos/{self._repo}/git/refs",
                headers=headers,
                payload={"ref": f"refs/heads/{branch}", "sha": sha},
            )
        except GitHubPullRequestError as exc:
            if "Reference already exists" in str(exc):
                return
            raise

    async def _create_file(self, headers: dict[str, str], draft: PullRequestDraft) -> None:
        encoded = base64.b64encode(draft.content.encode("utf-8")).decode("ascii")
        await _request_json(
            "PUT",
            f"{self._base_url}/repos/{self._repo}/contents/{draft.file_path}",
            headers=headers,
            payload={
                "message": f"Add SolBreach submission {draft.file_path}",
                "content": encoded,
                "branch": draft.branch,
            },
        )

    async def _create_pull_request(
        self, headers: dict[str, str], draft: PullRequestDraft
    ) -> PullRequestResult:
        try:
            data = await _request_json(
                "POST",
                f"{self._base_url}/repos/{self._repo}/pulls",
                headers=headers,
                payload={
                    "title": draft.title,
                    "head": draft.branch,
                    "base": self._base_branch,
                    "body": draft.body,
                },
            )
        except GitHubPullRequestError as exc:
            if "A pull request already exists" in str(exc):
                return PullRequestResult(
                    url=f"https://github.com/{self._repo}/tree/{draft.branch}",
                    number=None,
                )
            raise
        return PullRequestResult(url=str(data["html_url"]), number=int(data["number"]))


def make_submission_ref(wallet_or_user: str, submission_id: str) -> str:
    source = wallet_or_user or "user"
    safe_source = re.sub(r"[^a-zA-Z0-9._-]+", "-", source).strip("-").lower()
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", submission_id).strip("-").lower()
    return f"{safe_source}-{safe_id}"


async def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict | None = None,
) -> dict:
    return await to_thread(_request_json_sync, method, url, headers, payload)


def _request_json_sync(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict | None,
) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        message = _github_error_message(error_body)
        raise GitHubPullRequestError(f"{message} (GitHub HTTP {exc.code})") from exc
    except urllib.error.URLError as exc:
        raise GitHubPullRequestError(f"GitHub request failed: {exc.reason}") from exc


def _github_error_message(body: str) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return body or "GitHub request failed"
    message = data.get("message") or "GitHub request failed"
    errors = data.get("errors")
    if errors:
        return f"{message}: {errors}"
    return str(message)
