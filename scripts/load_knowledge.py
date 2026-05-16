from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy import select

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import KnowledgeDocument
from app.db.session import SessionLocal, engine, ensure_pgvector_extension
from app.rag.indexing import KnowledgeIndexer

ALLOWED_SOURCE_TYPES = {
    "company_profile",
    "technical_knowledge",
    "personality_question",
}


class ManifestError(ValueError):
    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed knowledge_documents and knowledge_chunks from a JSON manifest."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the JSON manifest file.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--replace",
        action="store_true",
        help="Delete matching knowledge documents before inserting new ones.",
    )
    mode.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip manifest entries that already exist.",
    )
    return parser.parse_args()


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_str(item: dict[str, Any], key: str) -> str:
    value = _normalize_optional_str(item.get(key))
    if value is None:
        raise ManifestError(f"manifest entry is missing required field: {key}")
    return value


def _resolve_manifest_path(manifest_path: str) -> Path:
    path = Path(manifest_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest file not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest JSON parse failed: {exc}") from exc

    if isinstance(raw, dict):
        raw = raw.get("documents")
    if not isinstance(raw, list):
        raise ManifestError("manifest root must be a list or an object with a 'documents' list")

    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ManifestError(f"manifest entry #{idx} must be an object")
    return raw


def _prepare_entry(item: dict[str, Any], *, manifest_dir: Path) -> dict[str, Any]:
    source_type = _require_str(item, "source_type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ManifestError(
            "source_type must be one of: company_profile, technical_knowledge, "
            "personality_question"
        )

    metadata = item.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ManifestError("metadata must be an object")

    raw_path = _normalize_optional_str(item.get("path"))
    raw_content = item.get("content")
    if raw_path and raw_content is not None:
        raise ManifestError("use either 'path' or 'content' in one manifest entry, not both")
    if not raw_path and raw_content is None:
        raise ManifestError("manifest entry must contain either 'path' or 'content'")

    company = _normalize_optional_str(item.get("company"))
    job_role = _normalize_optional_str(item.get("job_role"))
    difficulty = _normalize_optional_str(item.get("difficulty"))

    if raw_path:
        file_path = Path(raw_path)
        if not file_path.is_absolute():
            file_path = manifest_dir / file_path
        file_path = file_path.resolve()
        if not file_path.is_file():
            raise ManifestError(f"knowledge file not found: {file_path}")
        title = _normalize_optional_str(item.get("title")) or file_path.stem
        return {
            "source_type": source_type,
            "title": title,
            "company": company,
            "job_role": job_role,
            "difficulty": difficulty,
            "path": file_path,
            "metadata": metadata,
        }

    content = str(raw_content).strip()
    if not content:
        raise ManifestError("content must not be empty")
    title = _require_str(item, "title")
    return {
        "source_type": source_type,
        "title": title,
        "company": company,
        "job_role": job_role,
        "difficulty": difficulty,
        "content": content,
        "metadata": metadata,
    }


def _identity_filters(entry: dict[str, Any]) -> list[Any]:
    filters: list[Any] = [
        KnowledgeDocument.source_type == entry["source_type"],
        KnowledgeDocument.title == entry["title"],
    ]
    for field in ("company", "job_role", "difficulty"):
        value = entry[field]
        column = getattr(KnowledgeDocument, field)
        filters.append(column.is_(None) if value is None else column == value)
    return filters


def _find_existing_documents(db, entry: dict[str, Any]) -> list[KnowledgeDocument]:
    stmt = (
        select(KnowledgeDocument)
        .where(*_identity_filters(entry))
        .order_by(KnowledgeDocument.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _bootstrap_schema() -> None:
    ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)


def main() -> int:
    args = _parse_args()
    manifest_path = _resolve_manifest_path(args.manifest)
    manifest = _load_manifest(manifest_path)
    prepared_entries = [
        _prepare_entry(item, manifest_dir=manifest_path.parent)
        for item in manifest
    ]

    _bootstrap_schema()

    inserted = 0
    skipped = 0
    replaced = 0
    total_chunks = 0

    with SessionLocal() as db:
        indexer = KnowledgeIndexer(db)

        for idx, entry in enumerate(prepared_entries, start=1):
            existing = _find_existing_documents(db, entry)
            if existing:
                if args.skip_existing:
                    print(f"[skip] #{idx} {entry['title']} ({len(existing)} existing document(s))")
                    skipped += 1
                    continue
                if args.replace:
                    for document in existing:
                        db.delete(document)
                    db.flush()
                    replaced += len(existing)
                else:
                    raise ManifestError(
                        "matching knowledge document already exists. "
                        "Use --replace or --skip-existing.\n"
                        f"title={entry['title']} source_type={entry['source_type']}"
                    )

            try:
                if "path" in entry:
                    result = indexer.index_file(
                        source_type=entry["source_type"],
                        title=entry["title"],
                        path=entry["path"],
                        company=entry["company"],
                        job_role=entry["job_role"],
                        difficulty=entry["difficulty"],
                        metadata=entry["metadata"],
                    )
                else:
                    result = indexer.index_text(
                        source_type=entry["source_type"],
                        title=entry["title"],
                        content=entry["content"],
                        company=entry["company"],
                        job_role=entry["job_role"],
                        difficulty=entry["difficulty"],
                        metadata=entry["metadata"],
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise

            inserted += 1
            total_chunks += result.chunk_count
            print(
                "[ok] "
                f"#{idx} {entry['title']} -> knowledge_document_id={result.knowledge_document_id} "
                f"chunks={result.chunk_count} text_length={result.text_length}"
            )

    print(
        "[done] "
        f"inserted={inserted} skipped={skipped} replaced={replaced} total_chunks={total_chunks}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ManifestError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
