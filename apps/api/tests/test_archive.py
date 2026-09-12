import io
import zipfile

import pytest

from app.services.archive import UnsafeArchiveError, extract_safe


def _make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_extract_safe_keeps_allowed_source_files():
    zip_bytes = _make_zip(
        {
            "app/main.py": b"print('hi')",
            "app/component.tsx": b"export const X = () => null;",
            "README.md": b"# ignored, not a source extension",
        }
    )
    results = extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=10_000_000)
    paths = {p for p, _ in results}
    assert paths == {"app/main.py", "app/component.tsx"}


def test_extract_safe_rejects_zip_slip_relative():
    zip_bytes = _make_zip({"../../etc/evil.py": b"pwn"})
    with pytest.raises(UnsafeArchiveError):
        extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=10_000_000)


def test_extract_safe_rejects_absolute_path():
    zip_bytes = _make_zip({"/etc/evil.py": b"pwn"})
    with pytest.raises(UnsafeArchiveError):
        extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=10_000_000)


def test_extract_safe_ignores_node_modules_and_git():
    zip_bytes = _make_zip(
        {
            "node_modules/pkg/index.js": b"module.exports = {};",
            ".git/config": b"[core]",
            "src/index.js": b"console.log('ok');",
        }
    )
    results = extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=10_000_000)
    paths = {p for p, _ in results}
    assert paths == {"src/index.js"}


def test_extract_safe_ignores_env_and_key_files():
    zip_bytes = _make_zip(
        {
            ".env": b"SECRET=1",
            "server.key": b"-----BEGIN KEY-----",
            "id_rsa": b"-----BEGIN RSA-----",
            "app.py": b"print('ok')",
        }
    )
    results = extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=10_000_000)
    paths = {p for p, _ in results}
    assert paths == {"app.py"}


def test_extract_safe_rejects_too_many_files():
    zip_bytes = _make_zip({f"file_{i}.py": b"x" for i in range(5)})
    with pytest.raises(UnsafeArchiveError):
        extract_safe(zip_bytes, max_files=3, max_uncompressed_bytes=10_000_000)


def test_extract_safe_rejects_oversized_archive():
    zip_bytes = _make_zip({"big.py": b"x" * 1000})
    with pytest.raises(UnsafeArchiveError):
        extract_safe(zip_bytes, max_files=100, max_uncompressed_bytes=100)


def test_extract_safe_rejects_bad_zip_bytes():
    with pytest.raises(UnsafeArchiveError):
        extract_safe(b"not a zip", max_files=100, max_uncompressed_bytes=10_000_000)
