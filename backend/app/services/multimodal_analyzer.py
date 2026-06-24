import re
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


SIGNAL_KEYWORDS = [
    "error",
    "timeout",
    "failed",
    "unauthorized",
    "exception",
    "denied",
    "suspicious",
    "malware",
    "phishing",
    "database",
    "500",
    "502",
    "503",
    "504",
    "vpn",
    "network",
    "wifi",
    "password",
    "mfa",
    "login",
    "disk",
    "cpu",
    "memory",
    "server down",
]

RISK_KEYWORDS = {
    "security": ["unauthorized", "suspicious", "malware", "phishing", "unknown login"],
    "availability": ["500", "502", "503", "504", "timeout", "server down", "database", "exception"],
    "access": ["access denied", "denied", "password", "mfa", "login"],
}

HTTP_STATUS_RE = re.compile(r"\b([45]\d{2})\b")
EXCEPTION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_.]*(?:Exception|Error))\b")
LOG_LEVEL_RE = re.compile(r"\b(ERROR|WARN|WARNING|CRITICAL|FATAL)\b", re.IGNORECASE)
COMMON_ERROR_CODE_RE = re.compile(r"\b(HTTP\s*[45]\d{2}|[45]\d{2}|ORA-\d+|SQLSTATE\s*[A-Z0-9]+|ECONNRESET|ETIMEDOUT|EACCES)\b", re.IGNORECASE)


def _keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted({keyword for keyword in SIGNAL_KEYWORDS if keyword in lowered})


def analyze_screenshot_with_vision_model(file_name: str | None, file_path: str | Path | None = None) -> dict[str, Any]:
    """Local OCR implementation. It is not a vision model and reports failures explicitly."""
    if not file_name and not file_path:
        return {
            "screenshot_attached": False,
            "ocr_provider": "pytesseract",
            "ocr_status": "not_provided",
            "extracted_text": "",
            "confidence": None,
            "detected_keywords": [],
            "detected_error_codes": [],
            "error": None,
            "summary": "未上传截图",
        }
    if Image is None or pytesseract is None:
        return {
            "screenshot_attached": True,
            "ocr_provider": "pytesseract",
            "ocr_status": "unavailable",
            "extracted_text": "",
            "confidence": None,
            "detected_keywords": [],
            "detected_error_codes": [],
            "error": "Pillow 或 pytesseract 未安装，截图 OCR 已降级。",
            "summary": "截图已上传，但 OCR 组件不可用，未提取视觉文本证据。",
        }
    try:
        if not file_path:
            raise FileNotFoundError("截图路径为空，无法执行 OCR")
        image = Image.open(file_path)
        data = pytesseract.image_to_data(image, lang="eng+chi_sim", output_type=pytesseract.Output.DICT)
        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            cleaned = str(text).strip()
            if not cleaned:
                continue
            words.append(cleaned)
            try:
                value = float(conf)
                if value >= 0:
                    confidences.append(value)
            except (TypeError, ValueError):
                continue
        extracted_text = " ".join(words).strip()
        confidence = round(sum(confidences) / len(confidences), 2) if confidences else None
        return {
            "screenshot_attached": True,
            "ocr_provider": "pytesseract",
            "ocr_status": "success" if extracted_text else "no_text_detected",
            "extracted_text": extracted_text,
            "confidence": confidence,
            "detected_keywords": _keyword_hits(extracted_text),
            "detected_error_codes": sorted(set(COMMON_ERROR_CODE_RE.findall(extracted_text))),
            "error": None,
            "summary": "OCR 提取到截图文本证据" if extracted_text else "截图已处理，但未识别到可用文字。",
        }
    except Exception as exc:
        return {
            "screenshot_attached": True,
            "ocr_provider": "pytesseract",
            "ocr_status": "failed",
            "extracted_text": "",
            "confidence": None,
            "detected_keywords": [],
            "detected_error_codes": [],
            "error": str(exc),
            "summary": "截图 OCR 失败，系统已按无视觉文本证据降级处理。",
        }


def analyze_log_file(file_name: str | None = None, content: str | None = None, max_lines: int = 120) -> dict[str, Any]:
    lines = (content or "").splitlines()[:max_lines]
    sample = "\n".join(lines)
    searchable = f"{file_name or ''}\n{sample}"
    detected_keywords = _keyword_hits(searchable)
    http_statuses = sorted(set(HTTP_STATUS_RE.findall(searchable)))
    exceptions = sorted(set(EXCEPTION_RE.findall(searchable)))
    log_levels = [match.upper() for match in LOG_LEVEL_RE.findall(searchable)]
    warning_count = sum(1 for level in log_levels if level in {"WARN", "WARNING"})
    error_count = sum(1 for level in log_levels if level in {"ERROR", "CRITICAL", "FATAL"})
    structured_signals = {
        "error_count": error_count,
        "warning_count": warning_count,
        "http_statuses": http_statuses,
        "exceptions": exceptions[:10],
        "has_timeout": "timeout" in searchable.lower() or "timed out" in searchable.lower(),
        "has_database_signal": bool(re.search(r"\b(database|sql|jdbc|connection pool|数据库)\b", searchable, re.IGNORECASE)),
        "has_unauthorized_signal": bool(re.search(r"\b(unauthorized|forbidden|access denied|denied|未授权|拒绝访问)\b", searchable, re.IGNORECASE)),
    }
    return {
        "log_attached": bool(file_name),
        "file_name": file_name,
        "sample_line_count": len(lines),
        "sample_excerpt": sample[:1200],
        "detected_keywords": detected_keywords,
        "structured_signals": structured_signals,
        "summary": "日志证据：" + "、".join(detected_keywords) if detected_keywords else "日志中未检测到明显风险关键词",
    }


def combine_multimodal_signals(
    title: str,
    description: str,
    affected_system: str | None = None,
    screenshot_file_name: str | None = None,
    screenshot_file_path: str | Path | None = None,
    log_file_name: str | None = None,
    log_content: str | None = None,
) -> dict[str, Any]:
    text = f"{title}\n{description}\n{affected_system or ''}"
    text_keywords = _keyword_hits(text)
    screenshot_summary = analyze_screenshot_with_vision_model(screenshot_file_name, screenshot_file_path)
    log_summary = analyze_log_file(log_file_name, log_content)

    ocr_text = screenshot_summary.get("extracted_text", "")
    detected_keywords = sorted(set(text_keywords + log_summary["detected_keywords"] + screenshot_summary.get("detected_keywords", [])))
    risk_indicators: list[str] = []
    searchable = f"{text}\n{log_file_name or ''}\n{log_content or ''}\n{ocr_text}".lower()
    for risk_name, keywords in RISK_KEYWORDS.items():
        if any(keyword in searchable for keyword in keywords):
            risk_indicators.append(risk_name)

    evidence_items = [
        {
            "source_type": "text",
            "source_name": "ticket_description",
            "excerpt": text[:500],
            "signals": text_keywords,
            "available": bool(title or description or affected_system),
        }
    ]
    if log_file_name:
        evidence_items.append(
            {
                "source_type": "log",
                "source_name": log_file_name,
                "excerpt": log_summary.get("sample_excerpt", ""),
                "signals": log_summary.get("detected_keywords", []),
                "structured_signals": log_summary.get("structured_signals", {}),
                "available": bool(log_content),
            }
        )
    if screenshot_file_name or screenshot_file_path:
        evidence_items.append(
            {
                "source_type": "ocr",
                "source_name": screenshot_file_name or str(screenshot_file_path),
                "excerpt": ocr_text[:500],
                "signals": screenshot_summary.get("detected_keywords", []),
                "ocr_status": screenshot_summary.get("ocr_status"),
                "confidence": screenshot_summary.get("confidence"),
                "error": screenshot_summary.get("error"),
                "available": bool(ocr_text),
            }
        )

    extracted_signals = {
        "title_length": len(title),
        "description_length": len(description),
        "affected_system": affected_system,
        "has_screenshot": bool(screenshot_file_name or screenshot_file_path),
        "has_log": bool(log_file_name),
        "ocr_text_available": bool(ocr_text),
    }

    attachment_summary = {"screenshot": screenshot_summary, "log": log_summary}
    modality_summary = {
        "text": f"文本描述命中 {len(text_keywords)} 个关键词",
        "screenshot": screenshot_summary["summary"],
        "log": log_summary["summary"],
        "combined": f"综合证据命中 {len(detected_keywords)} 个关键词，风险类型：{', '.join(risk_indicators) if risk_indicators else '证据不足或暂无高危信号'}",
    }

    return {
        "extracted_signals": extracted_signals,
        "detected_keywords": detected_keywords,
        "attachment_summary": attachment_summary,
        "risk_indicators": risk_indicators,
        "modality_summary": modality_summary,
        "evidence": evidence_items,
        "ocr_text": ocr_text,
        "log_text": log_content or "",
    }


def read_log_preview(path: str | Path | None, max_chars: int = 12000) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""
