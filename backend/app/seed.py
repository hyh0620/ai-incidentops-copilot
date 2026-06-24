import argparse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, func, select

from app.database import create_db_and_tables, engine
from app.models import (
    AIReview,
    AIAnalysisAudit,
    AdminNote,
    AttachmentFileType,
    KnowledgeBaseChunk,
    KnowledgeBaseArticle,
    RemediationTask,
    RemediationTaskStatus,
    Ticket,
    TicketAttachment,
    TicketSeverity,
    TicketStatus,
    TicketTimelineEvent,
    User,
    UserRole,
)
from app.services.ticket_service import analyze_ticket
from app.core.config import get_settings
from app.services.rag_service import DEFAULT_INDEX_DIR, rebuild_kb_index


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


KB_ARTICLES = [
    {
        "title": "VPN 无法连接",
        "category": "网络连接",
        "summary": "排查 VPN 客户端、证书、网络出口和网关策略。",
        "content": "确认本地网络可用，检查 VPN 客户端版本、证书过期时间和多因素认证状态。如提示无法连接或网络超时，先切换网络重试，再查看网关日志。",
        "tags": ["VPN", "网络", "无法连接", "网络超时"],
        "reading_time": 4,
    },
    {
        "title": "密码重置失败",
        "category": "账号权限",
        "summary": "处理密码重置链接失效、账号锁定和 SSO 同步延迟。",
        "content": "检查用户账号状态、密码策略、单点登录同步任务和邮件投递。若出现密码校验失败或登录被拒绝，先解除锁定再触发密码重置。",
        "tags": ["密码", "登录", "账号"],
        "reading_time": 3,
    },
    {
        "title": "MFA 验证码无法接收",
        "category": "账号权限",
        "summary": "排查 MFA 绑定、短信/邮件通道和设备时间同步。",
        "content": "确认 MFA 设备绑定是否有效，检查验证码发送通道、用户时区和设备时间。必要时临时发放恢复码并要求重新绑定。",
        "tags": ["多因素认证", "登录", "验证码"],
        "reading_time": 3,
    },
    {
        "title": "可疑登录告警处理",
        "category": "安全风险",
        "summary": "针对异地登录、可疑 IP 和异常设备的处置流程。",
        "content": "发现可疑登录、未知地点登录或未授权访问时，应暂停会话、强制改密、核验登录 IP 和设备指纹，并上报安全运营团队。",
        "tags": ["可疑登录", "异地登录", "未授权访问"],
        "reading_time": 5,
    },
    {
        "title": "钓鱼邮件上报流程",
        "category": "安全风险",
        "summary": "识别钓鱼邮件并完成邮件隔离、样本上报和用户提醒。",
        "content": "用户怀疑钓鱼邮件或恶意软件附件时，保留邮件头和附件哈希，隔离可疑邮件，提醒用户不要点击链接，并提交安全运营复核。",
        "tags": ["钓鱼邮件", "恶意软件", "邮箱"],
        "reading_time": 4,
    },
    {
        "title": "软件安装被策略阻止",
        "category": "软件系统",
        "summary": "处理安装包被终端管控或软件白名单策略阻止。",
        "content": "确认安装包来源、软件白名单策略、终端安全客户端日志。必要时由 IT 管理员临时放行并记录审批单。",
        "tags": ["软件安装", "策略阻止", "终端管控"],
        "reading_time": 3,
    },
    {
        "title": "数据库连接超时",
        "category": "软件系统",
        "summary": "排查数据库连接超时、连接池耗尽和网络链路异常。",
        "content": "出现数据库连接超时时，检查连接池、慢查询、数据库实例健康状态和应用到数据库的网络连通性。",
        "tags": ["数据库", "连接超时", "连接池"],
        "reading_time": 5,
    },
    {
        "title": "生产 API 返回 500 错误",
        "category": "软件系统",
        "summary": "处理 API 500、异常堆栈和部署回滚判断。",
        "content": "生产 API 返回 500 错误时，检查最近发布、错误堆栈、上游依赖和数据库状态。必要时执行回滚并开启事故复盘。",
        "tags": ["API", "500", "异常"],
        "reading_time": 5,
    },
    {
        "title": "GitLab CI 构建失败",
        "category": "软件系统",
        "summary": "排查流水线构建失败、执行器离线和依赖缓存问题。",
        "content": "检查 GitLab CI 构建失败日志、执行器状态、依赖缓存、镜像拉取权限和最近提交差异。",
        "tags": ["GitLab", "持续集成", "构建失败"],
        "reading_time": 4,
    },
    {
        "title": "服务器磁盘空间不足",
        "category": "系统资源",
        "summary": "处理磁盘使用率、日志膨胀和容量告警。",
        "content": "服务器磁盘使用率达到阈值时，定位大文件、清理历史日志、检查备份任务，并规划磁盘扩容或日志归档策略。",
        "tags": ["磁盘", "服务器", "系统资源"],
        "reading_time": 4,
    },
    {
        "title": "内网系统访问被拒绝",
        "category": "账号权限",
        "summary": "处理访问被拒绝、权限组缺失和部门角色变更。",
        "content": "用户访问内网系统提示访问被拒绝时，检查用户部门、权限组、审批记录和单点登录同步状态。",
        "tags": ["访问被拒绝", "权限拒绝", "权限"],
        "reading_time": 3,
    },
    {
        "title": "邮箱收不到外部邮件",
        "category": "软件系统",
        "summary": "排查外部邮件投递、网关拦截和邮箱规则。",
        "content": "检查邮件网关日志、反垃圾策略、用户收件规则和域名 MX 配置，确认是否被隔离或退信。",
        "tags": ["邮箱", "邮件网关", "投递失败"],
        "reading_time": 3,
    },
]


TICKET_EXAMPLES = [
    ("在家办公无法连接企业 VPN", "员工在家办公时无法连接企业 VPN，切换无线网络后仍然提示连接超时。", "网络连接", "高", "企业 VPN"),
    ("账号出现异地可疑登录告警", "账号收到异地可疑登录告警，登录地点显示为海外 IP，用户怀疑存在未授权访问。", "安全风险", "高", "SSO"),
    ("无法访问 Jira 项目空间", "Jira 项目提示访问被拒绝，用户已转入新项目组但权限尚未同步。", "账号权限", "中", "Jira"),
    ("办公笔记本运行极慢", "笔记本运行缓慢，CPU 和内存长时间占用 95%，影响日常办公。", "硬件设备", "中", "办公电脑"),
    ("收到疑似钓鱼邮件", "用户收到疑似钓鱼邮件，邮件中包含外部链接和异常附件。", "安全风险", "高", "企业邮箱"),
    ("生产 API 返回 500 错误", "生产 API 返回 500 错误，接口日志出现后端异常堆栈。", "软件系统", "高", "生产 API"),
    ("数据库连接超时", "应用访问订单数据库时连接超时，偶发连接池耗尽。", "数据库", "高", "订单数据库"),
    ("MFA 验证码无法接收", "用户登录时收不到 MFA 验证码，无法完成二次认证。", "账号权限", "中", "SSO"),
    ("软件安装被终端策略阻止", "安装设计软件时被终端安全策略阻止，需要确认白名单和审批记录。", "软件系统", "低", "终端管理"),
    ("共享盘访问被拒绝", "访问部门共享盘时提示访问被拒绝，影响资料查看。", "账号权限", "中", "文件共享"),
    ("GitLab CI 构建失败", "GitLab CI 构建失败，流水线日志显示依赖安装失败。", "软件系统", "中", "GitLab"),
    ("内部数据看板返回空白页", "内部数据看板打开后返回空白页，浏览器控制台出现脚本异常。", "软件系统", "中", "BI Dashboard"),
    ("服务器磁盘使用率达到 95%", "应用服务器磁盘使用率达到 95%，日志目录增长过快。", "硬件设备", "高", "应用服务器"),
    ("检测到未知设备登录", "系统检测到未知设备登录，用户本人未确认该设备。", "安全风险", "高", "IAM"),
    ("部署后 API 请求超时", "部署后部分 API 请求超时，多个接口响应时间超过 30 秒。", "软件系统", "高", "支付 API"),
    ("会议室 WiFi 频繁断开", "会议室无线网络频繁断开，视频会议多次中断。", "网络连接", "中", "办公无线"),
    ("密码重置链接已失效", "密码重置链接已失效，多次重发后仍然无法完成重置。", "账号权限", "低", "SSO"),
    ("收不到外部客户邮件", "客户反馈外部邮件无法送达，邮箱网关暂未发现明显退信记录。", "软件系统", "中", "企业邮箱"),
    ("财务系统出现未授权访问提示", "财务系统提示未授权访问和权限拒绝，用户权限疑似异常。", "安全风险", "高", "财务系统"),
    ("数据库慢查询导致报表超时", "报表查询触发数据库慢查询并导致超时，业务等待时间过长。", "数据库", "高", "报表数据库"),
    ("终端出现恶意软件告警", "终端安全客户端提示恶意软件告警，可疑文件来自外部压缩包。", "安全风险", "高", "终端安全"),
    ("部门打印机无法连接", "部门打印机无法连接，同部门多名同事均无法正常打印。", "硬件设备", "低", "办公打印"),
    ("HR 系统登录失败", "HR 系统登录失败，提示密码错误或账号状态异常。", "账号权限", "中", "HR 系统"),
    ("应用服务器内存占用突增", "应用服务器内存占用突增，服务响应明显变慢。", "硬件设备", "高", "应用服务器"),
    ("CRM 页面返回 500 错误", "CRM 页面返回 500 错误，后端日志出现空指针异常。", "软件系统", "高", "CRM"),
    ("批处理任务无法连接数据库", "夜间批处理任务无法连接数据库，导致定时任务失败。", "数据库", "高", "批处理平台"),
    ("用户上报可疑钓鱼附件", "用户上报可疑钓鱼附件，附件疑似伪装成发票文件。", "安全风险", "高", "企业邮箱"),
    ("配置变更后内部 API 异常", "配置变更后内部 API 出现异常，接口错误率明显升高。", "软件系统", "高", "配置中心"),
    ("共享看板访问被拒绝", "共享数据看板提示访问被拒绝，新成员无法查看团队指标。", "账号权限", "中", "BI Dashboard"),
    ("分支机构访问总部系统延迟高", "分支机构访问总部系统延迟较高，多个内网业务系统响应缓慢。", "网络连接", "中", "广域网"),
]


def reset_database(session: Session) -> None:
    for model in [AIReview, AIAnalysisAudit, AdminNote, RemediationTask, TicketTimelineEvent, TicketAttachment, Ticket, KnowledgeBaseChunk, KnowledgeBaseArticle, User]:
        session.exec(delete(model))
    session.commit()


def seed_users(session: Session) -> list[User]:
    users = [
        User(name="王晨", email="wangchen@example.com", role=UserRole.requester, department="市场部"),
        User(name="李晓雨", email="lixiaoyu@example.com", role=UserRole.requester, department="财务部"),
        User(name="张弛", email="zhangchi@example.com", role=UserRole.requester, department="研发部"),
        User(name="陈安", email="chenan@example.com", role=UserRole.requester, department="运营部"),
        User(name="赵敏", email="zhaomin@example.com", role=UserRole.requester, department="人力资源"),
        User(name="周宁", email="zhouning@example.com", role=UserRole.requester, department="销售部"),
        User(name="林峰", email="linfeng.admin@example.com", role=UserRole.admin, department="IT 运维"),
        User(name="许静", email="xujing.admin@example.com", role=UserRole.admin, department="安全运营"),
    ]
    session.add_all(users)
    session.commit()
    for user in users:
        session.refresh(user)
    return users


def seed_kb(session: Session) -> None:
    session.add_all([KnowledgeBaseArticle(**article) for article in KB_ARTICLES])
    session.commit()


def demo_log_content(title: str, description: str, category: str, system: str) -> str:
    if category == "安全风险":
        return f"2026-05-01T10:15:00Z WARN 安全告警 {title}\n可疑登录 未授权访问 账号系统={system}\n{description}\n"
    if category == "数据库":
        return f"2026-05-01T10:15:00Z ERROR 数据库连接超时 {title}\n数据库连接超时 连接池耗尽 业务系统={system}\n{description}\n"
    if category == "网络连接":
        return f"2026-05-01T10:15:00Z WARN 网络连接异常 {title}\n网络超时 VPN 无法连接 业务系统={system}\n{description}\n"
    if category == "账号权限":
        return f"2026-05-01T10:15:00Z WARN 权限校验失败 {title}\n访问被拒绝 登录失败 权限同步延迟 业务系统={system}\n{description}\n"
    if category in {"硬件设备", "系统资源"}:
        return f"2026-05-01T10:15:00Z WARN 系统资源告警 {title}\nCPU 内存 磁盘使用率偏高 业务系统={system}\n{description}\n"
    return f"2026-05-01T10:15:00Z ERROR 软件系统异常 {title}\nHTTP 500 接口异常 请求超时 业务系统={system}\n{description}\n"


def seed_tickets(session: Session, users: list[User]) -> list[Ticket]:
    requester_users = [user for user in users if user.role == UserRole.requester]
    teams = ["一线服务台", "网络运维组", "平台工程组", "安全运营组", "身份与权限组"]
    statuses = [TicketStatus.triaged, TicketStatus.in_progress, TicketStatus.resolved, TicketStatus.open]
    tickets: list[Ticket] = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for index, (title, description, category, urgency, system) in enumerate(TICKET_EXAMPLES, start=1):
        user = requester_users[(index - 1) % len(requester_users)]
        created_at = datetime.utcnow() - timedelta(days=(30 - index) % 7, hours=index % 10)
        has_log = index in {2, 6, 7, 11, 13, 15, 20, 21, 25, 28}
        has_screenshot = index in {1, 3, 5, 8, 12, 19, 22, 27, 29}
        log_name = f"demo-ticket-{index}.log" if has_log else None
        screenshot_name = f"ticket-{index}-screenshot.png" if has_screenshot else None
        log_content = ""
        if log_name:
            log_path = UPLOAD_DIR / log_name
            log_content = demo_log_content(title, description, category, system)
            log_path.write_text(log_content, encoding="utf-8")

        status = statuses[index % len(statuses)]
        updated_at = created_at + timedelta(hours=6 + index)
        ticket = Ticket(
            requester_id=user.id,
            title=title,
            description=description,
            user_category=category,
            affected_system=system,
            urgency=urgency,
            status=TicketStatus.open,
            created_at=created_at,
            updated_at=updated_at,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        tickets.append(ticket)

        if screenshot_name:
            session.add(
                TicketAttachment(
                    ticket_id=ticket.id,
                    file_name=screenshot_name,
                    file_path=str(UPLOAD_DIR / screenshot_name),
                    file_type=AttachmentFileType.screenshot,
                    mime_type="image/png",
                    uploaded_at=created_at,
                )
            )
        if log_name:
            session.add(
                TicketAttachment(
                    ticket_id=ticket.id,
                    file_name=log_name,
                    file_path=str(UPLOAD_DIR / log_name),
                    file_type=AttachmentFileType.log,
                    mime_type="text/plain",
                    size_bytes=len(log_content.encode("utf-8")),
                    checksum=hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
                    uploaded_at=created_at,
                )
            )
        session.add(TicketTimelineEvent(ticket_id=ticket.id, event_type="created", content=f"{user.name} 提交工单", created_at=created_at))
        session.commit()
        analyze_ticket(session, ticket, event_type="ai_triaged")
        ticket.status = status
        ticket.assigned_team = teams[index % len(teams)] if status != TicketStatus.open else None
        ticket.created_at = created_at
        ticket.updated_at = updated_at
        session.add(ticket)
        if ticket.assigned_team:
            session.add(
                TicketTimelineEvent(
                    ticket_id=ticket.id,
                    event_type="assigned",
                    content=f"工单分配给 {ticket.assigned_team}",
                    created_at=created_at + timedelta(minutes=8),
                )
            )
        if status == TicketStatus.resolved:
            session.add(
                TicketTimelineEvent(
                    ticket_id=ticket.id,
                    event_type="resolved",
                    content="管理员已完成处理并等待用户确认",
                    created_at=updated_at,
                )
            )
        session.commit()
    return tickets


def seed_tasks_notes_reviews(session: Session, tickets: list[Ticket]) -> None:
    owners = ["林峰", "许静", "韩磊", "沈佳", "IT 值班组"]
    for index, ticket in enumerate(tickets[:15], start=1):
        task = RemediationTask(
            ticket_id=ticket.id,
            title=f"处置任务 #{index}: {ticket.predicted_category} 跟进",
            description=f"根据 AI 建议执行首轮排查：{ticket.next_steps[0] if ticket.next_steps else '补充信息'}",
            assigned_to=owners[index % len(owners)],
            status=[RemediationTaskStatus.todo, RemediationTaskStatus.in_progress, RemediationTaskStatus.done][index % 3],
            due_date=datetime.utcnow() + timedelta(days=index % 5 + 1),
            created_at=ticket.created_at + timedelta(minutes=12),
        )
        session.add(task)

    for ticket in tickets[3:13]:
        session.add(
            AdminNote(
                ticket_id=ticket.id,
                author="林峰",
                content=f"已确认影响系统为 {ticket.affected_system}，建议按 {ticket.predicted_category} 流程处理。",
                created_at=ticket.created_at + timedelta(minutes=20),
            )
        )

    review_candidates = [ticket for ticket in tickets if ticket.confidence < 0.7 or ticket.severity == TicketSeverity.high or ticket.predicted_category == "安全风险"][:8]
    for ticket in review_candidates:
        existing_review = session.exec(select(AIReview).where(AIReview.ticket_id == ticket.id)).first()
        if existing_review is not None:
            continue
        session.add(
            AIReview(
                ticket_id=ticket.id,
                original_category=ticket.predicted_category or "其他",
                original_severity=ticket.severity,
                review_reasons=["seed_demo_review"],
                status="pending",
                created_at=ticket.created_at + timedelta(minutes=4),
            )
        )
    session.commit()


def seed(reset: bool = False, ensure_schema: bool = False, rebuild_index: bool = True) -> None:
    if ensure_schema:
        create_db_and_tables()
    with Session(engine) as session:
        if reset:
            reset_database(session)
        existing = session.exec(select(func.count()).select_from(User)).one()
        if existing and not reset:
            print("Demo data already exists. Use --reset to rebuild it.")
            return
        users = seed_users(session)
        seed_kb(session)
        if rebuild_index:
            settings = get_settings()
            rebuild_kb_index(
                session,
                index_dir=DEFAULT_INDEX_DIR,
                force_fallback=settings.embedding_provider == "local_hash_embedding_fallback",
            )
        tickets = seed_tickets(session, users)
        seed_tasks_notes_reviews(session, tickets)
        print(f"Seed completed: {len(users)} users, {len(tickets)} tickets, {len(KB_ARTICLES)} KB articles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Clear existing demo tables before seeding")
    parser.add_argument("--dev-create-all", action="store_true", help="Development convenience only; prefer alembic upgrade head")
    parser.add_argument("--skip-index", action="store_true", help="Seed demo rows without rebuilding the local KB index")
    args = parser.parse_args()
    seed(reset=args.reset, ensure_schema=args.dev_create_all, rebuild_index=not args.skip_index)
