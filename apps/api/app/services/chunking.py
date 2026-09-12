"""Pure text/code chunking functions - no DB or network access, fully unit-testable."""
import ast
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentParseError(Exception):
    """Raised when a requirement document's bytes cannot be parsed as its declared type."""


@dataclass
class ChunkCandidate:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping fixed-size windows, breaking on whitespace where possible."""
    text = text.strip()
    if not text:
        return []
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    length = len(text)
    step = chunk_size - chunk_overlap

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start += step
    return chunks


def _extract_pdf_pages(content: bytes) -> list[tuple[str, int]]:
    try:
        reader = PdfReader(BytesIO(content))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            pages.append((page.extract_text() or "", i))
        return pages
    except PdfReadError as exc:
        raise DocumentParseError(f"Could not read PDF: {exc}") from exc


def parse_requirement_file(
    filename: str, content: bytes, chunk_size: int, chunk_overlap: int
) -> list[ChunkCandidate]:
    """Dispatch by extension, extract text, and split into chunk candidates with source metadata."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        candidates: list[ChunkCandidate] = []
        for page_text, page_number in _extract_pdf_pages(content):
            for chunk in chunk_text(page_text, chunk_size, chunk_overlap):
                candidates.append(
                    ChunkCandidate(text=chunk, metadata={"filename": filename, "page_number": page_number})
                )
        return candidates

    if lower.endswith(".txt") or lower.endswith(".md"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentParseError(f"Could not decode {filename} as UTF-8: {exc}") from exc
        return [
            ChunkCandidate(text=chunk, metadata={"filename": filename, "page_number": None})
            for chunk in chunk_text(text, chunk_size, chunk_overlap)
        ]

    raise DocumentParseError(f"Unsupported requirement file type: {filename}")


def _language_for(filepath: str) -> str:
    if filepath.endswith(".py"):
        return "python"
    if filepath.endswith((".ts", ".tsx")):
        return "typescript"
    return "javascript"


def chunk_python_code(source: str, filepath: str) -> list[ChunkCandidate]:
    """Chunk by top-level function/class using the stdlib AST; fall back to fixed-size windows."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [
            ChunkCandidate(
                text=chunk,
                metadata={
                    "file_path": filepath,
                    "language": "python",
                    "symbol_name": None,
                    "start_line": None,
                    "end_line": None,
                    "chunk_strategy": "fallback",
                },
            )
            for chunk in chunk_text(source, 1000, 150)
        ]

    lines = source.splitlines()
    candidates: list[ChunkCandidate] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            snippet = "\n".join(lines[start_line - 1 : end_line])
            candidates.append(
                ChunkCandidate(
                    text=snippet,
                    metadata={
                        "file_path": filepath,
                        "language": "python",
                        "symbol_name": node.name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "chunk_strategy": "ast",
                    },
                )
            )

    if not candidates:
        return [
            ChunkCandidate(
                text=chunk,
                metadata={
                    "file_path": filepath,
                    "language": "python",
                    "symbol_name": None,
                    "start_line": None,
                    "end_line": None,
                    "chunk_strategy": "fallback",
                },
            )
            for chunk in chunk_text(source, 1000, 150)
        ]
    return candidates


_JS_TOP_LEVEL_PATTERN = re.compile(
    r"^(export\s+)?(default\s+)?"
    r"(async\s+function\*?\s+\w+|function\*?\s+\w+|class\s+\w+"
    r"|const\s+\w+\s*=\s*(async\s*)?\([^)]*\)\s*=>"
    r"|const\s+\w+\s*=\s*(async\s*)?\w*\s*=>)",
    re.MULTILINE,
)


def chunk_js_ts_code(source: str, filepath: str) -> list[ChunkCandidate]:
    """Heuristically chunk on top-level function/class/arrow-const boundaries; fall back otherwise."""
    language = _language_for(filepath)
    matches = list(_JS_TOP_LEVEL_PATTERN.finditer(source))

    if not matches:
        return [
            ChunkCandidate(
                text=chunk,
                metadata={
                    "file_path": filepath,
                    "language": language,
                    "symbol_name": None,
                    "start_line": None,
                    "end_line": None,
                    "chunk_strategy": "fallback",
                },
            )
            for chunk in chunk_text(source, 1000, 150)
        ]

    candidates: list[ChunkCandidate] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        snippet = source[start:end].strip()
        if not snippet:
            continue
        start_line = source.count("\n", 0, start) + 1
        end_line = start_line + snippet.count("\n")
        name_match = re.search(r"(function\*?\s+(\w+)|class\s+(\w+)|const\s+(\w+))", match.group(0))
        symbol_name = next((g for g in (name_match.groups()[1:] if name_match else []) if g), None)
        candidates.append(
            ChunkCandidate(
                text=snippet,
                metadata={
                    "file_path": filepath,
                    "language": language,
                    "symbol_name": symbol_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "chunk_strategy": "heuristic",
                },
            )
        )
    return candidates


def chunk_code_file(source: str, filepath: str) -> list[ChunkCandidate]:
    if filepath.endswith(".py"):
        return chunk_python_code(source, filepath)
    return chunk_js_ts_code(source, filepath)
