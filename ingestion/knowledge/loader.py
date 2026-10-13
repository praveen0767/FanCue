"""Knowledge document loader and YAML frontmatter extractor."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from backend.app.schemas.knowledge import KnowledgeDocumentFrontmatter


class KnowledgeLoaderError(Exception):
    """Raised when knowledge document loading or YAML frontmatter parsing fails."""
    pass


class RawKnowledgeDocument:
    """In-memory representation of a parsed knowledge Markdown file."""

    def __init__(
        self,
        filepath: str,
        frontmatter: KnowledgeDocumentFrontmatter,
        body: str,
        is_draft: bool,
    ) -> None:
        self.filepath = filepath
        self.frontmatter = frontmatter
        self.body = body
        self.is_draft = is_draft

    @property
    def logical_id(self) -> str:
        return self.frontmatter.id


def parse_markdown_with_frontmatter(content: str, filepath: str = "") -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter delimited by '---' and separate markdown body."""
    if not content.startswith("---"):
        raise KnowledgeLoaderError(f"File {filepath} is missing opening '---' frontmatter delimiter.")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise KnowledgeLoaderError(f"File {filepath} has invalid frontmatter structure (missing closing '---').")

    frontmatter_yaml = parts[1].strip()
    body = parts[2].strip()

    try:
        raw_meta = yaml.safe_load(frontmatter_yaml)
    except Exception as e:
        raise KnowledgeLoaderError(f"Failed to parse YAML frontmatter in {filepath}: {e}") from e

    if not isinstance(raw_meta, dict):
        raise KnowledgeLoaderError(f"Frontmatter in {filepath} must be a YAML mapping.")

    return raw_meta, body


def load_knowledge_document(filepath: str, is_draft: bool = False) -> RawKnowledgeDocument:
    """Load a single markdown file and validate its frontmatter against Pydantic schema."""
    path = Path(filepath)
    if not path.is_file():
        raise KnowledgeLoaderError(f"File not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    raw_meta, body = parse_markdown_with_frontmatter(content, filepath=str(path))
    
    try:
        frontmatter = KnowledgeDocumentFrontmatter.model_validate(raw_meta)
    except Exception as e:
        raise KnowledgeLoaderError(f"Frontmatter schema validation failed in {filepath}: {e}") from e

    if not body:
        raise KnowledgeLoaderError(f"Markdown document body in {filepath} cannot be empty.")

    return RawKnowledgeDocument(
        filepath=str(path.resolve()),
        frontmatter=frontmatter,
        body=body,
        is_draft=is_draft,
    )


def load_knowledge_corpus(
    base_dir: str = "ingestion/knowledge",
    include_drafts: bool = False,
) -> List[RawKnowledgeDocument]:
    """Discover and load all knowledge documents in approved/ and optionally drafts/."""
    base_path = Path(base_dir)
    approved_dir = base_path / "approved"
    drafts_dir = base_path / "drafts"

    docs: List[RawKnowledgeDocument] = []

    if approved_dir.exists():
        for md_file in sorted(approved_dir.rglob("*.md")):
            docs.append(load_knowledge_document(str(md_file), is_draft=False))

    if include_drafts and drafts_dir.exists():
        for md_file in sorted(drafts_dir.rglob("*.md")):
            docs.append(load_knowledge_document(str(md_file), is_draft=True))

    return docs


def load_sources_registry(registry_path: str = "ingestion/knowledge/sources.yml") -> Dict[str, Any]:
    """Load the knowledge sources manifest."""
    path = Path(registry_path)
    if not path.is_file():
        raise KnowledgeLoaderError(f"Sources registry file not found: {registry_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "sources" not in data:
        raise KnowledgeLoaderError("Invalid sources.yml registry structure: missing 'sources' list.")

    return data
