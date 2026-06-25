import argparse
import json
from pathlib import Path

from app.database import create_db_and_tables, engine
from app.services.kb_ingestion_service import ingest_kb_file
from app.services.rag_service import DEFAULT_INDEX_DIR, index_status, rebuild_kb_index
from sqlmodel import Session


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local KB chunks and FAISS index for hybrid retrieval.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild chunks and local FAISS index")
    parser.add_argument("--check", action="store_true", help="Check DB chunks and index manifest consistency without rebuilding")
    parser.add_argument("--source", help="Import a Markdown, TXT, or PDF knowledge source and rebuild the local index")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="Directory for FAISS index and manifest")
    parser.add_argument("--force-fallback", action="store_true", help="Use deterministic local hash embeddings instead of sentence-transformers")
    parser.add_argument("--dev-create-all", action="store_true", help="Development convenience only; prefer alembic upgrade head")
    args = parser.parse_args()

    if args.dev_create_all:
        create_db_and_tables()
    with Session(engine) as session:
        source_ingested = False
        if args.source:
            run = ingest_kb_file(
                session,
                Path(args.source),
                rebuild_index=True,
                index_dir=Path(args.index_dir),
                force_fallback=args.force_fallback,
            )
            print(json.dumps({"ingestion_run": run.model_dump(mode="json")}, ensure_ascii=False, default=str))
            source_ingested = True
            if run.status == "failed":
                raise SystemExit(1)
        if args.rebuild and not source_ingested:
            manifest = rebuild_kb_index(session, index_dir=Path(args.index_dir), force_fallback=args.force_fallback)
            print(f"KB index rebuilt: chunks={len(manifest['chunk_ids'])}, provider={manifest['provider']}, faiss={manifest['faiss_enabled']}")
        if args.check:
            print(json.dumps(index_status(session, index_dir=Path(args.index_dir)), ensure_ascii=False, indent=2, default=str))
        if not args.rebuild and not args.check and not args.source:
            parser.error("Use --check, --source, or --rebuild.")


if __name__ == "__main__":
    main()
