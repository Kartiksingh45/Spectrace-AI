"""Download a public GitHub repository as a ZIP so it can go through the same safe-extraction
and chunking pipeline as a user-uploaded codebase archive - no `git` binary, no OAuth/API token,
just GitHub's public codeload endpoint (read-only, no repo write access is ever requested)."""
import httpx


class GithubImportError(Exception):
    """Raised when a repo's ZIP can't be downloaded (not found, private, too large, network error)."""


def download_repo_zip(owner: str, repo: str, branch: str, max_bytes: int) -> bytes:
    url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
            if response.status_code == 404:
                raise GithubImportError(
                    f"Repository {owner}/{repo} (branch {branch!r}) was not found, or is private"
                )
            response.raise_for_status()

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise GithubImportError(
                        f"Repository download exceeds the {max_bytes // (1024 * 1024)} MB limit"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as exc:
        raise GithubImportError(f"Could not download {owner}/{repo}: {exc}") from exc
