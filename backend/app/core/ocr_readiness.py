import time
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


try:
    import pytesseract
except Exception:  # pragma: no cover - import failure is covered by dependency injection tests
    pytesseract = None


DEFAULT_CACHE_TTL_SECONDS = 60.0
_CACHE: tuple[float, dict[str, Any]] | None = None


@dataclass(frozen=True)
class OCRProbe:
    provider: str
    required_languages: list[str]


def check_ocr_readiness(
    probe: OCRProbe | None = None,
    tesseract_module: Any | None = None,
    use_cache: bool = True,
    cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
) -> dict[str, Any]:
    settings = get_settings()
    probe = probe or OCRProbe(provider=settings.ocr_provider, required_languages=settings.ocr_required_language_list)
    global _CACHE

    if use_cache and _CACHE is not None:
        cached_at, cached_value = _CACHE
        if time.monotonic() - cached_at < cache_ttl_seconds:
            return cached_value

    result = _check_ocr_readiness_uncached(probe, tesseract_module)
    if use_cache:
        _CACHE = (time.monotonic(), result)
    return result


def clear_ocr_readiness_cache() -> None:
    global _CACHE
    _CACHE = None


def _check_ocr_readiness_uncached(probe: OCRProbe, tesseract_module: Any | None = None) -> dict[str, Any]:
    required_languages = probe.required_languages
    if probe.provider == "disabled":
        return {
            "provider": probe.provider,
            "python_package_available": False,
            "executable_available": False,
            "languages": [],
            "required_languages": required_languages,
            "ready": False,
            "degraded_reason": "OCR provider disabled by configuration.",
        }

    module = tesseract_module if tesseract_module is not None else pytesseract
    if module is None:
        return {
            "provider": probe.provider,
            "python_package_available": False,
            "executable_available": False,
            "languages": [],
            "required_languages": required_languages,
            "ready": False,
            "degraded_reason": "pytesseract Python package is not available.",
        }

    languages: list[str] = []
    executable_available = False
    try:
        module.get_tesseract_version()
        executable_available = True
    except Exception as exc:
        return {
            "provider": probe.provider,
            "python_package_available": True,
            "executable_available": False,
            "languages": languages,
            "required_languages": required_languages,
            "ready": False,
            "degraded_reason": f"Tesseract executable is unavailable: {exc}",
        }

    try:
        languages = sorted(str(language) for language in module.get_languages(config=""))
    except Exception as exc:
        return {
            "provider": probe.provider,
            "python_package_available": True,
            "executable_available": executable_available,
            "languages": languages,
            "required_languages": required_languages,
            "ready": False,
            "degraded_reason": f"Unable to list Tesseract languages: {exc}",
        }

    missing_languages = [language for language in required_languages if language not in languages]
    ready = executable_available and not missing_languages
    return {
        "provider": probe.provider,
        "python_package_available": True,
        "executable_available": executable_available,
        "languages": languages,
        "required_languages": required_languages,
        "ready": ready,
        "degraded_reason": None if ready else f"Missing OCR languages: {', '.join(missing_languages)}",
    }
