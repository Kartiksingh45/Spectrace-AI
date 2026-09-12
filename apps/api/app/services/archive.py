"""Safe extraction of an uploaded source-code ZIP - no filesystem writes, in-memory only."""
import posixpath
import zipfile
from io import BytesIO

ALLOWED_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx")

IGNORED_DIR_SEGMENTS = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "dist",
    "build",
    ".next",
}

IGNORED_FILENAME_PATTERNS = (".env",)
IGNORED_SUFFIXES = (".pem", ".key")
IGNORED_EXACT_NAMES = {"id_rsa", "id_ed25519"}


class UnsafeArchiveError(Exception):
    """Raised when a ZIP archive fails safety validation (path traversal, size, or count limits)."""


def _is_ignored(relpath: str) -> bool:
    parts = relpath.split("/")
    if any(part in IGNORED_DIR_SEGMENTS for part in parts[:-1]):
        return True
    filename = parts[-1]
    if filename.startswith(IGNORED_FILENAME_PATTERNS):
        return True
    if filename in IGNORED_EXACT_NAMES:
        return True
    if filename.endswith(IGNORED_SUFFIXES):
        return True
    return False


def _normalized_safe_path(raw_name: str) -> str | None:
    """Return a normalized, traversal-free relative path, or None if the entry is unsafe."""
    name = raw_name.replace("\\", "/")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return None  # absolute path (POSIX or Windows drive letter)

    normalized = posixpath.normpath(name)
    if normalized == "." or normalized.startswith("../") or normalized == "..":
        return None
    if posixpath.isabs(normalized):
        return None
    return normalized


def extract_safe(
    zip_bytes: bytes, max_files: int, max_uncompressed_bytes: int
) -> list[tuple[str, bytes]]:
    """Validate and extract allowed source files from a ZIP archive, entirely in memory.

    Raises UnsafeArchiveError on zip-slip attempts or when size/count limits are exceeded.
    Ignored directories, dotfiles, and non-source extensions are silently skipped (not an error).
    """
    try:
        zf = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise UnsafeArchiveError(f"Not a valid ZIP archive: {exc}") from exc

    infos = zf.infolist()
    if len(infos) > max_files:
        raise UnsafeArchiveError(f"Archive contains {len(infos)} entries, exceeding the limit of {max_files}")

    total_uncompressed = sum(info.file_size for info in infos)
    if total_uncompressed > max_uncompressed_bytes:
        raise UnsafeArchiveError(
            f"Archive uncompressed size {total_uncompressed} bytes exceeds the limit of {max_uncompressed_bytes}"
        )

    results: list[tuple[str, bytes]] = []
    for info in infos:
        if info.is_dir():
            continue

        safe_path = _normalized_safe_path(info.filename)
        if safe_path is None:
            raise UnsafeArchiveError(f"Unsafe path in archive: {info.filename!r}")

        if _is_ignored(safe_path):
            continue
        if not safe_path.endswith(ALLOWED_EXTENSIONS):
            continue

        results.append((safe_path, zf.read(info)))

    return results
