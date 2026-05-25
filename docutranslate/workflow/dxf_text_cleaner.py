# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
import re
import unicodedata
from dataclasses import dataclass


@dataclass(kw_only=True)
class DxfTextCleanerConfig:
    source_lang: str = "auto"
    target_lang: str = "auto"
    clean_text: bool = True
    filter_text: bool = True
    filter_empty: bool = True
    filter_number: bool = True
    filter_symbol: bool = True
    filter_code: bool = True
    filter_target_lang: bool = True
    filter_non_source_lang: bool = True


@dataclass
class DxfCleanResult:
    text: str
    status: str
    remark: str = ""

    @property
    def should_translate(self) -> bool:
        return self.status == "pending"


class DxfTextCleaner:
    _number_re = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?(?:\s*(?:mm|cm|m|kg|kpa|mpa|pa|v|kv|a|hz|kw|w|%|deg|\u00b0))?$",
        re.I,
    )
    _number_range_re = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?\s*(?:[-~\uff5e\u301c\u81f3\u5230]|\.\.)\s*[+-]?\d+(?:[.,]\d+)?"
        r"(?:\s*(?:mm|cm|m|kg|kpa|mpa|pa|v|kv|a|hz|kw|w|%|deg|\u00b0))?$",
        re.I,
    )
    _ratio_re = re.compile(r"^\d+(?:[.,]\d+)?\s*:\s*\d+(?:[.,]\d+)?$")
    _code_res = [
        re.compile(r"^[A-Z]$", re.I),
        re.compile(r"^[A-Z]{2,8}$"),
        re.compile(r"^[A-Z]{1,8}[-_.]?\d+[A-Z]?$", re.I),
        re.compile(r"^[A-Z]{1,8}-\d{1,6}[A-Z]?(?:-\d+)?$", re.I),
        re.compile(r"^(?:NO|REV|DWG|SHT|SHEET|P|M|T|D|A|B)\.?\s*-?\d+[A-Z]?$", re.I),
        re.compile(r"^[A-Z]*\d+[A-Z0-9]*$", re.I),
        re.compile(r"^(?:[A-Z]?\d+(?:[.,]\d+)?)(?:[*Xx\u00d7](?:[A-Z]?\d+(?:[.,]\d+)?))+$", re.I),
        re.compile(r"^\d+(?:\.\d+)+$"),
    ]
    _engineering_tag_re = re.compile(r"^[A-Z0-9][A-Z0-9_./+\-()]*[A-Z0-9+\-)]$", re.I)
    _parameter_token_re = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?(?:\s*[-~]\s*[+-]?\d+(?:[.,]\d+)?)?"
        r"\s*(?:mm|cm|m|kg|kpa|mpa|pa|vdc|vac|v|kv|ma|a|hz|khz|mhz|kw|w|%|deg|\u00b0)$",
        re.I,
    )

    def __init__(self, config: DxfTextCleanerConfig | None = None):
        self.config = config or DxfTextCleanerConfig()
        self._source_lang_key = self._language_key(self.config.source_lang)
        self._target_lang_key = self._language_key(self.config.target_lang)

    def clean(self, text: str | None) -> DxfCleanResult:
        cleaned = self._normalize(text or "") if self.config.clean_text else text or ""
        if self.config.filter_empty and not cleaned:
            return DxfCleanResult(cleaned, "filtered_empty")
        if not self.config.filter_text:
            return DxfCleanResult(cleaned, "pending")
        if self.config.filter_number and self._is_number(cleaned):
            return DxfCleanResult(cleaned, "filtered_number")
        if self.config.filter_symbol and self._is_symbol(cleaned):
            return DxfCleanResult(cleaned, "filtered_symbol")
        if self.config.filter_code and self._is_code(cleaned):
            return DxfCleanResult(cleaned, "filtered_code")
        if self.config.filter_target_lang and self._matches_target_lang(cleaned):
            return DxfCleanResult(cleaned, "filtered_target_lang")
        if self.config.filter_non_source_lang and not self._matches_source_lang(cleaned):
            return DxfCleanResult(cleaned, "filtered_non_source_lang")
        return DxfCleanResult(cleaned, "pending")

    def _normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        lines = [
            re.sub(r"[ \t\f\v]+", " ", line).strip()
            for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def _is_number(self, text: str) -> bool:
        value = text.strip()
        return bool(
            self._number_re.fullmatch(value)
            or self._number_range_re.fullmatch(value)
            or self._ratio_re.fullmatch(value)
        )

    def _is_symbol(self, text: str) -> bool:
        value = text.strip()
        if not value:
            return False
        return not any(char.isalnum() for char in value)

    def _is_code(self, text: str) -> bool:
        value = text.strip()
        if len(value) > 32:
            return False
        if any(ch.isspace() for ch in value) and not any(ch.isdigit() or ch in "-_./+()*Xx\u00d7" for ch in value):
            return False
        if "," in value or ";" in value:
            tokens = [token.strip() for token in re.split(r"[,;]+", value) if token.strip()]
            return bool(tokens) and all(self._is_nontranslatable_token(token) for token in tokens)
        return self._is_nontranslatable_token(value)

    def _is_nontranslatable_token(self, text: str) -> bool:
        value = text.strip()
        if self._is_number(value):
            return True
        if self._parameter_token_re.fullmatch(value):
            return True
        stripped = self._strip_wrapping_punctuation(value)
        no_space = re.sub(r"\s+", "", stripped)
        compact = re.sub(r"[\s\-_.]+", "", value)
        stripped_compact = re.sub(r"[\s\-_.]+", "", stripped)
        dimension = no_space
        return (
            any(pattern.fullmatch(value) for pattern in self._code_res)
            or any(pattern.fullmatch(stripped) for pattern in self._code_res)
            or any(pattern.fullmatch(compact) for pattern in self._code_res)
            or any(pattern.fullmatch(stripped_compact) for pattern in self._code_res)
            or any(pattern.fullmatch(dimension) for pattern in self._code_res)
            or self._is_engineering_tag(value)
            or self._is_engineering_tag(stripped)
            or self._is_engineering_tag(no_space)
        )

    def _strip_wrapping_punctuation(self, text: str) -> str:
        pairs = [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]
        value = text.strip()
        changed = True
        while changed and len(value) >= 2:
            changed = False
            for left, right in pairs:
                if value.startswith(left) and value.endswith(right):
                    value = value[1:-1].strip()
                    changed = True
                    break
        return value

    def _is_engineering_tag(self, text: str) -> bool:
        if " " in text or not self._engineering_tag_re.fullmatch(text):
            return False
        has_digit = any(char.isdigit() for char in text)
        has_upper = any("A" <= char <= "Z" for char in text.upper())
        has_tag_symbol = any(char in text for char in "-_./+()")
        has_unit = bool(re.search(r"\d+(?:VDC|VAC|V|A|MA|KW|W|HZ|KPA|MPA|MM|CM|M)\b", text, re.I))
        return has_upper and (has_digit or has_tag_symbol or has_unit)

    def _matches_source_lang(self, text: str) -> bool:
        source_lang = self._source_lang_key
        if not source_lang:
            return True
        if source_lang == "zh":
            return self._has_chinese(text)
        if source_lang == "en":
            return self._has_english(text)
        if source_lang == "ja":
            return self._has_japanese(text)
        if source_lang == "ko":
            return self._has_korean(text)
        return True

    def _matches_target_lang(self, text: str) -> bool:
        target_lang = self._target_lang_key
        if not target_lang:
            return False
        if target_lang == "zh":
            return self._is_mostly_chinese(text)
        if target_lang == "en":
            return self._is_mostly_english(text)
        if target_lang == "ja":
            return self._has_japanese(text)
        if target_lang == "ko":
            return self._has_korean(text)
        return False

    def _language_key(self, lang: str | None) -> str:
        value = (lang or "auto").lower()
        if value in {"", "auto", "unknown"}:
            return ""
        if any(key in value for key in ["zh", "chinese", "cn", "\u4e2d\u6587", "\u7b80\u4f53", "\u7e41\u4f53"]):
            return "zh"
        if any(key in value for key in ["en", "english"]):
            return "en"
        if any(key in value for key in ["ja", "japanese", "\u65e5\u672c"]):
            return "ja"
        if any(key in value for key in ["ko", "korean", "\ud55c\uad6d"]):
            return "ko"
        return ""

    def _has_chinese(self, text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _has_english(self, text: str) -> bool:
        return bool(re.search(r"[A-Za-z]", text))

    def _has_japanese(self, text: str) -> bool:
        return bool(re.search(r"[\u3040-\u30ff]", text)) or self._has_chinese(text)

    def _has_korean(self, text: str) -> bool:
        return bool(re.search(r"[\uac00-\ud7af]", text))

    def _is_mostly_chinese(self, text: str) -> bool:
        has_chinese = self._has_chinese(text)
        has_kana_or_korean = bool(re.search(r"[\u3040-\u30ff\uac00-\ud7af]", text))
        return has_chinese and not has_kana_or_korean and not self._has_english(text)

    def _is_mostly_english(self, text: str) -> bool:
        return self._has_english(text) and not bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))
