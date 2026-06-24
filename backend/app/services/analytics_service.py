from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import AIReview, KnowledgeBaseArticle, RemediationTask, Ticket, TicketSeverity, TicketStatus


def summary(session: Session) -> dict:
    tickets = session.exec(select(Ticket)).all()
    now = datetime.utcnow()
    pending = [item for item in tickets if item.status in {TicketStatus.open, TicketStatus.triaged, TicketStatus.in_progress}]
    high_risk = [item for item in tickets if item.severity in {TicketSeverity.high, TicketSeverity.critical}]
    resolved = [item for item in tickets if item.status in {TicketStatus.resolved, TicketStatus.closed}]
    avg_resolution_hours = 0.0
    if resolved:
        avg_resolution_hours = sum((item.updated_at - item.created_at).total_seconds() / 3600 for item in resolved) / len(resolved)
    today_new = [item for item in tickets if item.created_at.date() == now.date()]
    reviews = session.exec(select(AIReview)).all()
    return {
        "total_tickets": len(tickets),
        "pending_tickets": len(pending),
        "high_risk_tickets": len(high_risk),
        "avg_resolution_hours": round(avg_resolution_hours, 1),
        "today_new_tickets": len(today_new),
        "ai_review_pending": len([item for item in reviews if item.status == "pending"]),
    }


def category_distribution(session: Session) -> list[dict]:
    tickets = session.exec(select(Ticket)).all()
    counts = Counter(item.predicted_category or item.user_category for item in tickets)
    return [{"name": name, "value": value} for name, value in counts.most_common()]


def severity_distribution(session: Session) -> list[dict]:
    tickets = session.exec(select(Ticket)).all()
    counts = Counter(item.severity.value for item in tickets)
    return [{"name": name, "value": counts.get(name, 0)} for name in ["low", "medium", "high", "critical"]]


def seven_day_trend(session: Session) -> list[dict]:
    tickets = session.exec(select(Ticket)).all()
    today = datetime.utcnow().date()
    buckets = {today - timedelta(days=offset): 0 for offset in range(6, -1, -1)}
    for ticket in tickets:
        day = ticket.created_at.date()
        if day in buckets:
            buckets[day] += 1
    return [{"date": day.strftime("%m-%d"), "count": count} for day, count in buckets.items()]


def top_issues(session: Session) -> list[dict]:
    tickets = session.exec(select(Ticket)).all()
    counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        key = ticket.title.split(" from ")[0].split(" after ")[0]
        counts[key] += 1
    return [{"title": title, "count": count} for title, count in Counter(counts).most_common(6)]


def kb_hits(session: Session) -> list[dict]:
    articles = session.exec(select(KnowledgeBaseArticle).order_by(KnowledgeBaseArticle.hit_count.desc())).all()
    return [{"title": item.title, "hit_count": item.hit_count} for item in articles[:8]]


def ai_confidence_distribution(session: Session) -> list[dict]:
    tickets = session.exec(select(Ticket)).all()
    buckets = {"0.4-0.6": 0, "0.6-0.7": 0, "0.7-0.85": 0, "0.85-1.0": 0}
    for ticket in tickets:
        if ticket.confidence < 0.6:
            buckets["0.4-0.6"] += 1
        elif ticket.confidence < 0.7:
            buckets["0.6-0.7"] += 1
        elif ticket.confidence < 0.85:
            buckets["0.7-0.85"] += 1
        else:
            buckets["0.85-1.0"] += 1
    return [{"name": name, "value": value} for name, value in buckets.items()]


def average_resolution(session: Session) -> dict:
    tickets = session.exec(select(Ticket)).all()
    resolved = [item for item in tickets if item.status in {TicketStatus.resolved, TicketStatus.closed}]
    if not resolved:
        return {"avg_hours": 0, "resolved_count": 0}
    avg_hours = sum((item.updated_at - item.created_at).total_seconds() / 3600 for item in resolved) / len(resolved)
    tasks = session.exec(select(RemediationTask)).all()
    return {"avg_hours": round(avg_hours, 1), "resolved_count": len(resolved), "done_tasks": len([item for item in tasks if item.status == "done"])}
