import json

from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.database import engine
from app.models import KnowledgeBaseArticle, Ticket, User
from app.seed import seed
from app.services.rag_service import DEFAULT_INDEX_DIR, index_status, rebuild_kb_index


def main() -> None:
    settings = get_settings()
    with Session(engine) as session:
        user_count = session.exec(select(func.count()).select_from(User)).one()
        ticket_count = session.exec(select(func.count()).select_from(Ticket)).one()
        kb_count = session.exec(select(func.count()).select_from(KnowledgeBaseArticle)).one()
        if user_count < 8 or ticket_count < 30 or kb_count < 12:
            seed(reset=bool(user_count or ticket_count or kb_count), ensure_schema=False, rebuild_index=True)
            print(
                json.dumps(
                    {
                        "bootstrap": "seeded_demo_data_and_index",
                        "reason": "missing_or_partial_demo_fixture",
                        "previous_counts": {
                            "users": user_count,
                            "tickets": ticket_count,
                            "kb_articles": kb_count,
                        },
                    },
                    ensure_ascii=False,
                )
            )
            return

        status = index_status(session, index_dir=DEFAULT_INDEX_DIR)
        if not status.get("ready"):
            manifest = rebuild_kb_index(
                session,
                index_dir=DEFAULT_INDEX_DIR,
                force_fallback=settings.embedding_provider == "local_hash_embedding_fallback",
            )
            print(
                json.dumps(
                    {
                        "bootstrap": "rebuilt_stale_or_missing_index",
                        "chunk_count": manifest.get("chunk_count"),
                        "provider": manifest.get("provider"),
                    },
                    ensure_ascii=False,
                )
            )
            return

        print(json.dumps({"bootstrap": "ready_noop"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
