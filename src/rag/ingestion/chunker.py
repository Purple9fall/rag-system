from __future__ import annotations

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import MetadataMode


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Cat theo heading Markdown truoc, sau do cat tiep theo cau neu qua dai."""
    nodes = MarkdownNodeParser()([Document(text=text)])
    nodes = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)(nodes)
    chunks = [n.get_content(metadata_mode=MetadataMode.NONE).strip() for n in nodes]
    return [c for c in chunks if c]
