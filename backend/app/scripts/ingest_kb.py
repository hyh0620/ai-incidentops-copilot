import argparse
import hashlib
import json
from pathlib import Path

from app.database import create_db_and_tables, engine
from app.models import KnowledgeBaseArticle
from app.services.rag_service import DEFAULT_INDEX_DIR, index_status, rebuild_kb_index
from sqlmodel import Session, select


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _article_from_text(path: Path, text: str) -> dict:
    title = path.stem
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:10]:
        if line.startswith("#"):
            title = line.lstrip("#").strip() or title
            break
    content = "\n".join(line for line in lines if not line.startswith("#")) or text
    return {
        "title": title,
        "category": "其他",
        "summary": content[:160],
        "content": content,
        "tags": [],
        "reading_time": max(1, min(10, len(content) // 600 + 1)),
    }


def _load_source(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        records = payload if isinstance(payload, list) else payload.get("articles", [payload])
        return [dict(record) for record in records]
    return [_article_from_text(path, text)]


def import_source(session: Session, source: Path) -> dict:
    records = _load_source(source)
    upserted = 0
    for index, record in enumerate(records, start=1):
        content = str(record.get("content") or "")
        checksum = _checksum(json.dumps(record, ensure_ascii=False, sort_keys=True))
        article = session.exec(select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.source_checksum == checksum)).first()
        if article is None:
            article = KnowledgeBaseArticle(
                title=str(record.get("title") or source.stem),
                category=str(record.get("category") or "其他"),
                summary=str(record.get("summary") or content[:160]),
                content=content,
                tags=list(record.get("tags") or []),
                reading_time=int(record.get("reading_time") or max(1, len(content) // 600 + 1)),
                source_name=f"{source.name}#{index}",
                source_type=source.suffix.lower().lstrip(".") or "txt",
                source_checksum=checksum,
                version=str(record.get("version") or "v1"),
                ingestion_status="ready",
                index_status="stale",
            )
        else:
            article.title = str(record.get("title") or article.title)
            article.category = str(record.get("category") or article.category)
            article.summary = str(record.get("summary") or article.summary)
            article.content = content or article.content
            article.tags = list(record.get("tags") or article.tags)
            article.reading_time = int(record.get("reading_time") or article.reading_time)
            article.index_status = "stale"
        session.add(article)
        upserted += 1
    session.commit()
    return {"source": str(source), "upserted": upserted}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local KB chunks and FAISS index for hybrid retrieval.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild chunks and local FAISS index")
    parser.add_argument("--check", action="store_true", help="Check DB chunks and index manifest consistency without rebuilding")
    parser.add_argument("--source", help="Import a Markdown, TXT, or JSON knowledge source before optional rebuild")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="Directory for FAISS index and manifest")
    parser.add_argument("--force-fallback", action="store_true", help="Use deterministic local hash embeddings instead of sentence-transformers")
    parser.add_argument("--dev-create-all", action="store_true", help="Development convenience only; prefer alembic upgrade head")
    args = parser.parse_args()

    if args.dev_create_all:
        create_db_and_tables()
    with Session(engine) as session:
        if args.source:
            imported = import_source(session, Path(args.source))
            print(json.dumps({"import": imported}, ensure_ascii=False))
        if args.rebuild:
            manifest = rebuild_kb_index(session, index_dir=Path(args.index_dir), force_fallback=args.force_fallback)
            print(f"KB index rebuilt: chunks={len(manifest['chunk_ids'])}, provider={manifest['provider']}, faiss={manifest['faiss_enabled']}")
        if args.check:
            print(json.dumps(index_status(session, index_dir=Path(args.index_dir)), ensure_ascii=False, indent=2, default=str))
        if not args.rebuild and not args.check and not args.source:
            parser.error("Use --check, --source, or --rebuild.")


if __name__ == "__main__":
    main()
