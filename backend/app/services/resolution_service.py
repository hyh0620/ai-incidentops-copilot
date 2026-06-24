from app.models import TicketSeverity


RESOLUTION_PLAYBOOKS = {
    "网络连接": [
        "检查本地网络连接与 DNS 解析是否正常",
        "确认 VPN 客户端版本与证书状态",
        "重新认证账号并清理客户端缓存",
        "如仍失败，转交网络运维团队排查网关日志",
    ],
    "安全风险": [
        "暂停可疑账号会话并保留审计证据",
        "要求用户立即修改密码并重新绑定 MFA",
        "检查登录 IP、设备指纹和邮件来源",
        "上报安全运营团队进行威胁复核与封禁处置",
    ],
    "账号权限": [
        "确认账号状态、部门权限和最近权限变更记录",
        "检查 SSO/MFA 配置与验证码发送通道",
        "重新同步权限组或重置登录凭证",
        "如涉及核心系统，转交 IAM 团队复核",
    ],
    "软件系统": [
        "检查最近部署记录与变更窗口",
        "查看应用日志、错误堆栈和接口状态码",
        "检查数据库连接池、缓存和上游依赖",
        "转交后端或平台团队进行根因定位",
    ],
    "系统资源": [
        "检查服务器磁盘、CPU、内存和进程占用",
        "清理临时文件或扩容资源配额",
        "确认监控告警阈值与近期流量变化",
        "转交基础设施团队跟进容量治理",
    ],
    "其他": [
        "补充影响范围、复现步骤和业务优先级",
        "根据受影响系统查询最近变更记录",
        "先按普通工单分配一线支持处理",
        "必要时升级给对应系统负责人",
    ],
}


def generate_resolution(
    category: str,
    severity: TicketSeverity,
    related_kb_articles: list[dict],
) -> dict[str, object]:
    evidence_sources = [
        article
        for article in related_kb_articles
        if article.get("chunk_id") and article.get("evidence_excerpt") and article.get("final_score", 0) > 0
    ]
    if not evidence_sources:
        return {
            "suggested_resolution": "未找到足够知识库证据，建议人工复核后再制定处置方案。",
            "next_steps": [
                "补充错误截图、日志片段或受影响系统信息",
                "由一线服务台确认影响范围和业务优先级",
                "人工检索知识库或升级给对应系统负责人",
            ],
            "evidence_citations": [],
        }

    steps = RESOLUTION_PLAYBOOKS.get(category, RESOLUTION_PLAYBOOKS["其他"])
    citations = []
    for source in evidence_sources[:3]:
        excerpt = source["evidence_excerpt"]
        citations.append(f"《{source['title']}》chunk#{source['chunk_id']}：{excerpt[:160]}")

    urgency_hint = "该事件严重等级较高，请优先分配二线团队并保留处理证据。" if severity in {TicketSeverity.high, TicketSeverity.critical} else "可按标准 SLA 处理并持续跟踪用户反馈。"
    suggested_resolution = f"基于本地知识库证据，建议按「{category}」流程处理。{urgency_hint} 主要证据：{citations[0]}"
    evidence_steps = [f"参考证据 {index + 1}: {citation}" for index, citation in enumerate(citations)]
    return {"suggested_resolution": suggested_resolution, "next_steps": steps + evidence_steps, "evidence_citations": citations}
