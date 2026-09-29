from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedDocument:
    source_path: str
    markdown: str
    parser: str
    page_count: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_document(path: str | Path) -> ParsedDocument:
    """Parse a local immutable evidence document with Docling.

    OCR policy stays inside Docling; callers must preserve the original RAW file
    and treat this output as derived evidence.
    """
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source)
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except ImportError as exc:
        raise RuntimeError("document parsing requires the research extra with Docling") from exc

    result = DocumentConverter().convert(str(source))
    document = result.document
    markdown = document.export_to_markdown()
    page_count: int | None = None
    pages = getattr(document, "pages", None)
    if pages is not None:
        try:
            page_count = len(pages)
        except TypeError:
            page_count = None
    return ParsedDocument(
        source_path=str(source),
        markdown=markdown,
        parser="docling",
        page_count=page_count,
    )
