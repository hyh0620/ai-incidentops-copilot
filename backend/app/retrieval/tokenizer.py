import re
import warnings

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API", category=UserWarning)
        import jieba
except Exception:  # pragma: no cover
    jieba = None


TOKEN_RE = re.compile(
    r"ORA-\d+|SQLSTATE\s*[A-Z0-9]+|HTTP\s*[45]\d{2}|[45]\d{2}|[A-Z][A-Za-z0-9_]*(?:Exception|Error)|ECONNRESET|ETIMEDOUT|EACCES|[A-Za-z][A-Za-z0-9_.:-]{1,}|[\u4e00-\u9fff]{2,}",
    re.IGNORECASE,
)

TOKEN_SYNONYMS = {
    "cannot": ["无法"],
    "connect": ["连接"],
    "network": ["网络"],
    "wifi": ["无线"],
    "password": ["密码"],
    "login": ["登录"],
    "mfa": ["多因素认证", "验证码"],
    "access": ["访问", "权限"],
    "denied": ["拒绝"],
    "unauthorized": ["未授权"],
    "suspicious": ["可疑"],
    "unknown": ["未知", "异地"],
    "phishing": ["钓鱼"],
    "malware": ["恶意软件"],
    "database": ["数据库"],
    "timeout": ["超时"],
    "api": ["接口"],
    "exception": ["异常"],
    "error": ["错误"],
    "failed": ["失败"],
    "failure": ["失败"],
    "pipeline": ["流水线"],
    "runner": ["执行器"],
    "disk": ["磁盘"],
    "usage": ["使用率"],
    "cpu": ["cpu"],
    "memory": ["内存"],
    "server": ["服务器"],
    "policy": ["策略"],
    "blocked": ["阻止"],
    "email": ["邮件", "邮箱"],
    "mail": ["邮件", "邮箱"],
    "gateway": ["网关"],
}


def tokenize(text: str) -> list[str]:
    base = [match.group(0).lower().replace(" ", "") for match in TOKEN_RE.finditer(text)]
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    if jieba is not None and chinese:
        base.extend(token.lower() for token in jieba.cut(chinese) if len(token.strip()) >= 2)
    expanded = list(base)
    for token in base:
        expanded.extend(TOKEN_SYNONYMS.get(token, []))
    stop = {"the", "and", "or", "to", "of", "in", "from", "with", "after"}
    return [token for token in expanded if token not in stop]
