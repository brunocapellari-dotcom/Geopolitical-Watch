from __future__ import annotations

import re
from dataclasses import asdict, dataclass


_ARABIC = re.compile(r"[\u0600-\u06ff]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")


@dataclass(frozen=True)
class TextEnvelope:
    original_text: str
    original_language: str
    translated_text: str | None = None
    translated_language: str | None = None
    detection_method: str = "geowatch-language-v1"
    translation_method: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_language(text: str, *, declared_language: str | None = None) -> tuple[str, str]:
    if declared_language and declared_language.strip():
        return declared_language.strip().casefold(), "declared"
    sample = text.strip()
    if not sample:
        return "und", "empty"
    try:
        from lingua import LanguageDetectorBuilder  # type: ignore
        detector = LanguageDetectorBuilder.from_all_languages().build()
        language = detector.detect_language_of(sample)
        if language is not None:
            iso = language.iso_code_639_1
            if iso is not None:
                return iso.name.casefold(), "lingua"
    except ImportError:
        pass
    if _ARABIC.search(sample):
        return "ar", "unicode-script"
    if _CYRILLIC.search(sample):
        return "und-Cyrl", "unicode-script"
    return "und", "fallback"


def envelope_text(text: str, *, declared_language: str | None = None) -> TextEnvelope:
    language, method = detect_language(text, declared_language=declared_language)
    return TextEnvelope(
        original_text=text,
        original_language=language,
        detection_method=method,
    )


def attach_translation(
    envelope: TextEnvelope,
    *,
    translated_text: str,
    translated_language: str,
    method: str,
) -> TextEnvelope:
    """Attach an externally produced translation without ever replacing the original."""
    if not translated_text.strip():
        raise ValueError("translated_text must not be empty")
    if not translated_language.strip() or not method.strip():
        raise ValueError("translated_language and method are required")
    return TextEnvelope(
        original_text=envelope.original_text,
        original_language=envelope.original_language,
        translated_text=translated_text,
        translated_language=translated_language.strip().casefold(),
        detection_method=envelope.detection_method,
        translation_method=method.strip(),
    )
