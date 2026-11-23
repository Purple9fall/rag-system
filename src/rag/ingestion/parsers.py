from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MIN_CHARS = 50

DOCLING_EXT = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".md",
    ".png", ".jpg", ".jpeg", ".tiff",
}
UNSTRUCTURED_EXT = {
    ".doc", ".ppt", ".rtf", ".odt", ".epub", ".eml", ".msg",
    ".txt", ".csv", ".xml",
}

_docling_converter = None


@dataclass
class ParsedDoc:
    text: str
    parser: str


def parse_docling(path: Path) -> str:
    global _docling_converter
    if _docling_converter is None:
        from docling.document_converter import DocumentConverter

        _docling_converter = DocumentConverter()
    result = _docling_converter.convert(str(path))
    return result.document.export_to_markdown()


def parse_unstructured(path: Path) -> str:
    from unstructured.partition.auto import partition

    elements = partition(filename=str(path))
    return "\n\n".join(el.text for el in elements if getattr(el, "text", None))


def parse_tika(path: Path) -> str:
    from tika import parser

    parsed = parser.from_file(str(path))
    return (parsed.get("content") or "").strip()


PARSERS = {
    "docling": parse_docling,
    "unstructured": parse_unstructured,
    "tika": parse_tika,
}


def parser_order(ext: str) -> list[str]:
    if ext in DOCLING_EXT:
        return ["docling", "unstructured", "tika"]
    if ext in UNSTRUCTURED_EXT:
        return ["unstructured", "tika"]
    return ["tika", "unstructured"]


def parse_file(path: Path) -> ParsedDoc:
    """Thu lan luot cac parser; parser nao tra ve du noi dung thi dung."""
    errors: list[str] = []
    for name in parser_order(path.suffix.lower()):
        try:
            text = PARSERS[name](path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
            continue
        if len(text.strip()) >= MIN_CHARS:
            return ParsedDoc(text=text, parser=name)
        errors.append(f"{name}: noi dung qua ngan")
    raise ValueError(f"Khong parser nao doc duoc {path.name} ({'; '.join(errors)})")
