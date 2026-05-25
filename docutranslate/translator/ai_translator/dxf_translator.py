# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
import asyncio
import csv
import io
import re
from dataclasses import dataclass
from typing import Literal

import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode
from ezdxf.lldxf.tags import DXFTag
from ezdxf.render.mleader import make_mtext
from ezdxf.tools.text import estimate_mtext_extents
from ezdxf.tools.text_size import mtext_size

from docutranslate.agents.segments_agent import SegmentsTranslateAgent, SegmentsTranslateAgentConfig
from docutranslate.ir.document import Document
from docutranslate.translator.ai_translator.base import AiTranslator, AiTranslatorConfig
from docutranslate.workflow.dxf_layout import DxfLayoutAdjuster, DxfLayoutConfig
from docutranslate.workflow.dxf_mtext import rebuild_mtext_content, wrap_mtext_plain_text
from docutranslate.workflow.dxf_text_cleaner import DxfCleanResult, DxfTextCleaner, DxfTextCleanerConfig


DEFAULT_DXF_PROMPT = (
    "Translate short CAD engineering drawing labels. Keep terminology accurate, concise, and suitable for DXF write-back. "
    "Do not explain, expand, or add unrelated content. Preserve numbers, units, model names, variables, symbols, and line structure."
)

DEFAULT_DXF_AI_FILTER_PROMPT = (
    "You are a CAD engineering drawing text filter. For each input segment, decide whether it should be translated. "
    "Output exactly KEEP if the segment should be translated, or SKIP if it should not be translated. Do not translate the text. "
    "Use a conservative rule: when unsure, output KEEP so useful text is not accidentally skipped. "
    "KEEP table headers, column headers, row labels, drawing titles, natural-language notes, labels, descriptions, and other readable content that benefits from translation. "
    "KEEP uppercase table headers and acronyms when they act as headers or labels, unless the text is already in the target language. "
    "SKIP pure numbers, symbols, drawing numbers, device tags, model numbers, terminal IDs, parameters, units, electrical codes, "
    "or text already in the target language. Preserve the one-to-one segment order and return only KEEP or SKIP for each segment."
)

DXF_UNICODE_STYLE_PREFIX = "DocuTranslate_Unicode"
DXF_UNICODE_STYLE_FONTS = {
    "Arabic": "arial.ttf",
    "CJK": "simsun.ttc",
    "Devanagari": "mangal.ttf",
    "Generic": "arialuni.ttf",
    "Greek": "arial.ttf",
    "Japanese": "msgothic.ttc",
    "Korean": "malgun.ttf",
    "Latin": "arial.ttf",
    "Thai": "tahoma.ttf",
}

DXF_CAD_SAFE_SYMBOLS = str.maketrans(
    {
        "\uff5e": "~",
        "\u301c": "~",
    }
)


@dataclass
class DxfTranslatorConfig(AiTranslatorConfig):
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = "\n"
    source_lang: str = "auto"
    clean_text: bool = True
    filter_text: bool = True
    filter_empty: bool = True
    filter_number: bool = True
    filter_symbol: bool = True
    filter_code: bool = True
    filter_target_lang: bool = True
    filter_non_source_lang: bool = True
    ai_filter_enable: bool = True
    ai_filter_prompt: str | None = None
    min_layout_scale: float = 0.65


@dataclass
class DxfTableCellTarget:
    table: object
    table_handle: str
    layout_name: str
    row: int
    col: int
    cell_index: int
    tag_start: int
    tag_end: int
    text: str
    text_tag_indices: list[int]
    text_tag_code: int

    def dxftype(self) -> str:
        return "ACAD_TABLE_CELL"

    @property
    def key(self) -> str:
        return f"{self.table_handle}:CELL:{self.row}:{self.col}"


@dataclass
class DxfMLeaderTextTarget:
    entity: object
    entity_handle: str
    layout_name: str
    mtext_data: object
    text: str
    original_content: str

    def dxftype(self) -> str:
        return self.entity.dxftype()

    @property
    def key(self) -> str:
        return f"{self.entity_handle}:MLEADER_TEXT"


class DxfTranslator(AiTranslator):
    """Translate TEXT, MTEXT, and block ATTRIB entities in a DXF document."""

    def __init__(self, config: DxfTranslatorConfig):
        super().__init__(config=config)
        self.chunk_size = config.chunk_size
        self.insert_mode = config.insert_mode
        self.separator = config.separator
        self.translate_agent = None
        self.ai_filter_agent = None
        self.ai_filter_enable = config.ai_filter_enable
        self.total_chunks = 0
        self.records: list[dict] = []
        self._entity_by_handle: dict[str, object] = {}
        self._entity_doc_id: int | None = None
        self._encoded_text_cache: dict[str, str] = {}
        self._wrapped_mtext_cache: dict[tuple[str, float, float], str] = {}
        self._mtext_content_cache: dict[tuple[str, str, float, float], str] = {}
        self._style_cache: dict[str, str] = {}
        self._updated_table_graphic_entities: set[str] = set()
        self.statistics = self._empty_statistics()
        self.cleaner = DxfTextCleaner(
            DxfTextCleanerConfig(
                source_lang=config.source_lang,
                target_lang=config.to_lang,
                clean_text=config.clean_text,
                filter_text=config.filter_text,
                filter_empty=config.filter_empty,
                filter_number=config.filter_number,
                filter_symbol=config.filter_symbol,
                filter_code=config.filter_code,
                filter_target_lang=config.filter_target_lang,
                filter_non_source_lang=config.filter_non_source_lang,
            )
        )
        self.layout_adjuster = DxfLayoutAdjuster(DxfLayoutConfig(min_scale=config.min_layout_scale))

        glossary_dict = self.glossary.glossary_dict if self.glossary else None
        if not self.skip_translate:
            def progress_callback(current: int, total: int):
                self.total_chunks = total
                if self.progress_tracker:
                    percent = 30 + int((current / total) * 60)
                    self.progress_tracker.update(
                        percent=percent,
                        message=f"Translating DXF text ({current}/{total})",
                    )

            agent_config = SegmentsTranslateAgentConfig(
                custom_prompt=config.custom_prompt or DEFAULT_DXF_PROMPT,
                to_lang=config.to_lang,
                base_url=config.base_url,
                api_key=config.api_key,
                model_id=config.model_id,
                temperature=config.temperature,
                top_p=config.top_p,
                thinking=config.thinking,
                concurrent=config.concurrent,
                timeout=config.timeout,
                logger=self.logger,
                glossary_dict=glossary_dict,
                retry=config.retry,
                system_proxy_enable=config.system_proxy_enable,
                force_json=config.force_json,
                rpm=config.rpm,
                tpm=config.tpm,
                provider=config.provider,
                progress_callback=progress_callback,
                extra_body=config.extra_body,
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)

            if config.ai_filter_enable:
                def ai_filter_progress_callback(current: int, total: int):
                    if self.progress_tracker:
                        percent = 20 + int((current / total) * 10)
                        self.progress_tracker.update(
                            percent=percent,
                            message=f"AI filtering DXF text ({current}/{total})",
                        )

                ai_filter_agent_config = SegmentsTranslateAgentConfig(
                    custom_prompt=config.ai_filter_prompt or DEFAULT_DXF_AI_FILTER_PROMPT,
                    to_lang="KEEP or SKIP",
                    base_url=config.base_url,
                    api_key=config.api_key,
                    model_id=config.model_id,
                    temperature=config.temperature,
                    top_p=config.top_p,
                    thinking=config.thinking,
                    concurrent=config.concurrent,
                    timeout=config.timeout,
                    logger=self.logger,
                    glossary_dict=None,
                    retry=config.retry,
                    system_proxy_enable=config.system_proxy_enable,
                    force_json=config.force_json,
                    rpm=config.rpm,
                    tpm=config.tpm,
                    provider=config.provider,
                    progress_callback=ai_filter_progress_callback,
                    extra_body=config.extra_body,
                )
                self.ai_filter_agent = SegmentsTranslateAgent(ai_filter_agent_config)

    def _empty_statistics(self) -> dict:
        return {
            "total_entities": 0,
            "filtered_count": 0,
            "valid_text_count": 0,
            "unique_text_count": 0,
            "duplicate_count": 0,
            "translated_count": 0,
            "translate_failed_count": 0,
            "writeback_success_count": 0,
            "writeback_failed_count": 0,
        }

    def _decode_content(self, content: bytes) -> str:
        for encoding in ("utf-8-sig", "gbk", "cp936", "latin1"):
            try:
                return content.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")

    def _load_dxf(self, document: Document):
        text = self._decode_content(document.content)
        return ezdxf.read(io.StringIO(text))

    def _iter_text_entities(self, dxf_doc):
        for layout in dxf_doc.layouts:
            layout_name = layout.name
            for entity in layout:
                entity_type = entity.dxftype()
                if entity_type in {"TEXT", "MTEXT"}:
                    yield layout_name, entity
                elif entity_type in {"MLEADER", "MULTILEADER"}:
                    target = self._mleader_text_target(layout_name, entity)
                    if target:
                        yield layout_name, target
                elif entity_type == "ACAD_TABLE":
                    for cell in self._iter_table_cells(layout_name, entity):
                        yield layout_name, cell
                elif entity_type == "INSERT":
                    for attrib in getattr(entity, "attribs", []):
                        setattr(attrib, "_docutranslate_block_name", entity.dxf.name)
                        yield layout_name, attrib
        for block in dxf_doc.blocks:
            if block.name.startswith("*") or getattr(block.block_record, "is_xref", False):
                continue
            layout_name = f"BLOCK:{block.name}"
            for entity in block:
                if entity.dxftype() in {"TEXT", "MTEXT"}:
                    setattr(entity, "_docutranslate_block_name", block.name)
                    yield layout_name, entity

    def _get_text(self, entity) -> str:
        if isinstance(entity, DxfTableCellTarget):
            return decode_dxf_unicode(entity.text or "")
        if isinstance(entity, DxfMLeaderTextTarget):
            return decode_dxf_unicode(entity.text or "")
        if entity.dxftype() in {"TEXT", "ATTRIB"}:
            return decode_dxf_unicode(entity.dxf.text or "")
        if hasattr(entity, "plain_text"):
            return decode_dxf_unicode(entity.plain_text() or "")
        return decode_dxf_unicode(getattr(entity, "text", "") or "")

    def _encode_dxf_unicode(self, text: str) -> str:
        cache_key = text
        cached_text = self._encoded_text_cache.get(cache_key)
        if cached_text is not None:
            return cached_text
        text = text.translate(DXF_CAD_SAFE_SYMBOLS)
        if text.isascii():
            self._encoded_text_cache[cache_key] = text
            return text
        parts = []
        for char in text:
            codepoint = ord(char)
            if codepoint > 0xFFFF:
                parts.append(f"\\U+{codepoint:08x}")
            elif codepoint > 0x7F:
                parts.append(f"\\U+{codepoint:04x}")
            else:
                parts.append(char)
        encoded_text = "".join(parts)
        self._encoded_text_cache[cache_key] = encoded_text
        return encoded_text

    def _has_non_ascii(self, text: str) -> bool:
        return not text.isascii()

    def _style_family_for_text(self, text: str) -> str:
        for char in text:
            codepoint = ord(char)
            if 0xAC00 <= codepoint <= 0xD7AF:
                return "Korean"
            if 0x3040 <= codepoint <= 0x30FF:
                return "Japanese"
            if 0x4E00 <= codepoint <= 0x9FFF:
                return "CJK"
            if 0x0600 <= codepoint <= 0x06FF or 0x0750 <= codepoint <= 0x077F or 0x08A0 <= codepoint <= 0x08FF:
                return "Arabic"
            if 0x0900 <= codepoint <= 0x097F:
                return "Devanagari"
            if 0x0E00 <= codepoint <= 0x0E7F:
                return "Thai"
            if 0x0370 <= codepoint <= 0x03FF:
                return "Greek"
            if 0x0400 <= codepoint <= 0x04FF or 0x00C0 <= codepoint <= 0x024F:
                return "Latin"
        return "Generic"

    def _ensure_unicode_style(self, dxf_doc, text: str) -> str:
        family = self._style_family_for_text(text)
        cached_style = self._style_cache.get(family)
        if cached_style:
            return cached_style
        style_name = f"{DXF_UNICODE_STYLE_PREFIX}_{family}"
        font = DXF_UNICODE_STYLE_FONTS[family]
        doc_styles = dxf_doc.styles
        if style_name not in doc_styles:
            doc_styles.new(style_name, dxfattribs={"font": font})
        self._style_cache[family] = style_name
        return style_name

    def _set_text(self, entity, text: str, style_name: str | None = None):
        if isinstance(entity, DxfTableCellTarget):
            return self._set_table_cell_text(entity, text)
        if isinstance(entity, DxfMLeaderTextTarget):
            return self._set_mleader_text(entity, text, style_name=style_name)
        if style_name and hasattr(entity.dxf, "style"):
            entity.dxf.style = style_name
        if entity.dxftype() in {"TEXT", "ATTRIB"}:
            content = self._encode_dxf_unicode(text)
            entity.dxf.text = content
            return content
        width = float(entity.dxf.get("width", 0.0) or 0.0)
        char_height = float(entity.dxf.get("char_height", 0.0) or 0.0)
        wrap_key = (text, width, char_height)
        wrapped_text = self._wrapped_mtext_cache.get(wrap_key)
        if wrapped_text is None:
            wrapped_text = wrap_mtext_plain_text(text, width, char_height)
            self._wrapped_mtext_cache[wrap_key] = wrapped_text
        original_content = entity.text or ""
        content_key = (original_content, wrapped_text, width, char_height)
        content = self._mtext_content_cache.get(content_key)
        if content is None:
            content = rebuild_mtext_content(original_content, wrapped_text, self._encode_dxf_unicode)
            self._mtext_content_cache[content_key] = content
        if hasattr(entity, "set_content"):
            entity.set_content(content)
        elif hasattr(entity, "set_text"):
            entity.set_text(content)
        else:
            entity.text = content
        self._refresh_mtext_layout_bounds(entity)
        return content

    def _refresh_mtext_layout_bounds(self, entity):
        if entity.dxftype() != "MTEXT":
            return
        for attr in ("rect_width", "rect_height", "defined_height"):
            try:
                entity.dxf.discard(attr)
            except Exception:
                pass
        try:
            size = mtext_size(entity)
            width = size.column_width or size.total_width
            height = size.total_height
        except Exception:
            width, height = estimate_mtext_extents(entity)
        column_width = float(entity.dxf.get("width", 0.0) or 0.0)
        if column_width > 0:
            width = max(width, column_width)
        if width > 0:
            entity.dxf.rect_width = width
        if height > 0:
            entity.dxf.rect_height = height
            if not entity.has_columns:
                entity.dxf.defined_height = height

    def _compose_text(self, original: str, translated: str) -> str:
        if self.insert_mode == "append":
            return original + self.separator + translated
        if self.insert_mode == "prepend":
            return translated + self.separator + original
        return translated

    def _entity_key(self, entity) -> str:
        if isinstance(entity, (DxfTableCellTarget, DxfMLeaderTextTarget)):
            return entity.key
        return getattr(entity.dxf, "handle", "")

    def _mleader_text_target(self, layout_name: str, entity) -> DxfMLeaderTextTarget | None:
        mtext_data = getattr(getattr(entity, "context", None), "mtext", None)
        if mtext_data is None:
            return None
        original_content = decode_dxf_unicode(getattr(mtext_data, "default_content", "") or "")
        try:
            text = decode_dxf_unicode(make_mtext(entity).plain_text() or "")
        except Exception:
            text = original_content
        if not text:
            return None
        entity_handle = getattr(entity.dxf, "handle", "") or str(id(entity))
        return DxfMLeaderTextTarget(
            entity=entity,
            entity_handle=entity_handle,
            layout_name=layout_name,
            mtext_data=mtext_data,
            text=text,
            original_content=original_content,
        )

    def _set_mleader_text(self, target: DxfMLeaderTextTarget, text: str, style_name: str | None = None) -> str:
        if style_name:
            self._set_mleader_style(target, style_name)
        content = rebuild_mtext_content(target.original_content, text, self._encode_dxf_unicode)
        target.mtext_data.default_content = content
        target.text = text
        target.original_content = content
        if hasattr(target.entity, "update_proxy_graphic"):
            target.entity.update_proxy_graphic()
        return content

    def _set_mleader_style(self, target: DxfMLeaderTextTarget, style_name: str):
        doc = getattr(target.entity, "doc", None)
        if doc is None:
            return
        style = doc.styles.get(style_name)
        if style is None:
            return
        if hasattr(target.entity.dxf, "text_style_handle"):
            target.entity.dxf.text_style_handle = style.dxf.handle
        if hasattr(target.mtext_data, "style_handle"):
            target.mtext_data.style_handle = style.dxf.handle

    def _iter_table_cells(self, layout_name: str, table) -> list[DxfTableCellTarget]:
        if not hasattr(table, "xtags"):
            return []
        try:
            tags = table.xtags.get_subclass("AcDbTable")
        except Exception:
            return []

        n_cols = int(tags.get_first_value(92, 0) or 0)
        split_code = 301 if tags.has_tag(302) else 171
        table_handle = getattr(table.dxf, "handle", "") or ""
        targets: list[DxfTableCellTarget] = []
        group_start = None
        cell_index = 0

        for index, tag in enumerate(tags):
            if tag.code == split_code:
                if group_start is not None:
                    target = self._table_cell_target_from_tags(
                        table,
                        table_handle,
                        layout_name,
                        tags,
                        group_start,
                        index,
                        cell_index,
                        n_cols,
                    )
                    if target:
                        targets.append(target)
                    cell_index += 1
                group_start = index
        if group_start is not None:
            target = self._table_cell_target_from_tags(
                table,
                table_handle,
                layout_name,
                tags,
                group_start,
                len(tags),
                cell_index,
                n_cols,
            )
            if target:
                targets.append(target)
        return targets

    def _table_cell_target_from_tags(
        self,
        table,
        table_handle: str,
        layout_name: str,
        tags,
        start: int,
        end: int,
        cell_index: int,
        n_cols: int,
    ) -> DxfTableCellTarget | None:
        text_tag_indices = [index for index in range(start, end) if tags[index].code == 302]
        text_tag_code = 302
        if text_tag_indices:
            text = str(tags[text_tag_indices[0]].value or "")
        else:
            text_tag_indices = [index for index in range(start, end) if tags[index].code in {1, 2, 3}]
            text_tag_code = 1
            text = "".join(str(tags[index].value or "") for index in text_tag_indices)
        if not text_tag_indices:
            return None
        row = cell_index // n_cols if n_cols else 0
        col = cell_index % n_cols if n_cols else cell_index
        return DxfTableCellTarget(
            table=table,
            table_handle=table_handle,
            layout_name=layout_name,
            row=row,
            col=col,
            cell_index=cell_index,
            tag_start=start,
            tag_end=end,
            text=text,
            text_tag_indices=text_tag_indices,
            text_tag_code=text_tag_code,
        )

    def _set_table_cell_text(self, target: DxfTableCellTarget, text: str) -> str:
        content = self._encode_dxf_unicode(text)
        tags = target.table.xtags.get_subclass("AcDbTable")
        self._set_table_cell_text_tags(tags, target, content)
        self._set_table_graphic_text(target, text)
        target.text = text
        return content

    def _set_table_cell_text_tags(self, tags, target: DxfTableCellTarget, content: str):
        cell_text_indices = [
            index
            for index in range(target.tag_start, target.tag_end)
            if tags[index].code in {1, 2, 3, 302}
        ]
        primary_indices = [index for index in cell_text_indices if tags[index].code == target.text_tag_code]
        secondary_indices = [index for index in cell_text_indices if tags[index].code != target.text_tag_code]
        for indices in (primary_indices, secondary_indices):
            if not indices:
                continue
            tags[indices[0]] = DXFTag(tags[indices[0]].code, content)
            for index in indices[1:]:
                tags[index] = DXFTag(tags[index].code, "")

    def _set_table_graphic_text(self, target: DxfTableCellTarget, text: str):
        doc = getattr(target.table, "doc", None)
        if doc is None:
            return
        block_name = getattr(target.table.dxf, "geometry", "") or ""
        if not block_name:
            return
        try:
            block = doc.blocks.get(block_name)
        except Exception:
            return
        if block is None:
            return
        entity = self._find_table_graphic_text_entity(block, decode_dxf_unicode(target.text or ""))
        if entity is None:
            return
        style_name = self._ensure_unicode_style(doc, text) if self._has_non_ascii(text) else None
        self._set_text(entity, text, style_name=style_name)

    def _find_table_graphic_text_entity(self, block, original_text: str):
        fallback_entity = None
        for entity in block:
            if entity.dxftype() not in {"TEXT", "MTEXT"}:
                continue
            entity_key = getattr(entity.dxf, "handle", "") or str(id(entity))
            if entity_key in self._updated_table_graphic_entities:
                continue
            if fallback_entity is None:
                fallback_entity = entity
            if self._get_text(entity) == original_text:
                self._updated_table_graphic_entities.add(entity_key)
                return entity
        if fallback_entity is not None:
            entity_key = getattr(fallback_entity.dxf, "handle", "") or str(id(fallback_entity))
            self._updated_table_graphic_entities.add(entity_key)
        return fallback_entity

    def _dump_dxf(self, dxf_doc) -> bytes:
        stream = io.StringIO()
        dxf_doc.write(stream)
        return dxf_doc.encode(stream.getvalue())

    def _entity_metadata(self, entity, layout_name: str, record_id: int, original_text: str, cleaned_text: str, status: str, remark: str = "") -> dict:
        if isinstance(entity, DxfTableCellTarget):
            return {
                "id": record_id,
                "entity_handle": entity.key,
                "entity_type": entity.dxftype(),
                "layout_name": layout_name,
                "original_text": original_text,
                "cleaned_text": cleaned_text,
                "translated_text": "",
                "mtext_rebuilt_text": "",
                "block_name": "",
                "attrib_tag": "",
                "table_row": entity.row,
                "table_col": entity.col,
                "insert_point": "",
                "height": "",
                "width": "",
                "rotation": "",
                "alignment": "",
                "style": "",
                "layer": getattr(entity.table.dxf, "layer", ""),
                "status": status,
                "remark": remark,
            }
        if isinstance(entity, DxfMLeaderTextTarget):
            mtext_data = entity.mtext_data
            return {
                "id": record_id,
                "entity_handle": entity.key,
                "entity_type": entity.dxftype(),
                "layout_name": layout_name,
                "original_text": original_text,
                "cleaned_text": cleaned_text,
                "translated_text": "",
                "mtext_rebuilt_text": "",
                "block_name": "",
                "attrib_tag": "",
                "table_row": "",
                "table_col": "",
                "insert_point": str(getattr(mtext_data, "insert", "")),
                "height": getattr(getattr(entity.entity, "context", None), "char_height", ""),
                "width": getattr(mtext_data, "width", ""),
                "rotation": getattr(mtext_data, "rotation", ""),
                "alignment": getattr(mtext_data, "alignment", ""),
                "style": getattr(mtext_data, "style_handle", ""),
                "layer": getattr(entity.entity.dxf, "layer", ""),
                "status": status,
                "remark": remark,
            }
        insert = getattr(entity.dxf, "insert", None)
        return {
            "id": record_id,
            "entity_handle": getattr(entity.dxf, "handle", ""),
            "entity_type": entity.dxftype(),
            "layout_name": layout_name,
            "original_text": original_text,
            "cleaned_text": cleaned_text,
            "translated_text": "",
            "mtext_rebuilt_text": "",
            "block_name": getattr(entity, "_docutranslate_block_name", ""),
            "attrib_tag": getattr(entity.dxf, "tag", ""),
            "table_row": "",
            "table_col": "",
            "insert_point": str(insert) if insert is not None else "",
            "height": getattr(entity.dxf, "height", getattr(entity.dxf, "char_height", "")),
            "width": getattr(entity.dxf, "width", ""),
            "rotation": getattr(entity.dxf, "rotation", ""),
            "alignment": getattr(entity.dxf, "halign", getattr(entity.dxf, "attachment_point", "")),
            "style": getattr(entity.dxf, "style", ""),
            "layer": getattr(entity.dxf, "layer", ""),
            "status": status,
            "remark": remark,
        }

    def _extract_records(self, dxf_doc) -> tuple[list[tuple], list[str]]:
        self.records = []
        self._entity_by_handle = {}
        self._entity_doc_id = id(dxf_doc)
        self._encoded_text_cache = {}
        self._wrapped_mtext_cache = {}
        self._mtext_content_cache = {}
        self._style_cache = {}
        self._updated_table_graphic_entities = set()
        valid_texts = []
        seen_text_ids: dict[str, int] = {}
        clean_cache = {}
        duplicate_count = 0
        for index, (layout_name, entity) in enumerate(self._iter_text_entities(dxf_doc), start=1):
            original_text = self._get_text(entity)
            clean_result = clean_cache.get(original_text)
            if clean_result is None:
                clean_result = self.cleaner.clean(original_text)
                clean_cache[original_text] = clean_result
            if self._should_translate_table_header_code(entity, clean_result):
                clean_result = DxfCleanResult(clean_result.text, "pending", "Table header acronym forced to translate.")
            status = "pending" if clean_result.should_translate else clean_result.status
            remark = clean_result.remark
            if clean_result.should_translate:
                if clean_result.text in seen_text_ids:
                    status = "filtered_duplicate"
                    remark = f"Duplicate of id {seen_text_ids[clean_result.text]}."
                    duplicate_count += 1
                else:
                    seen_text_ids[clean_result.text] = index
                    valid_texts.append(clean_result.text)
            record = self._entity_metadata(
                entity,
                layout_name,
                index,
                original_text,
                clean_result.text,
                status,
                remark,
            )
            self.records.append(record)
            entity_key = self._entity_key(entity)
            if entity_key:
                self._entity_by_handle[entity_key] = entity

        unique_texts = valid_texts
        self.statistics["total_entities"] = len(self.records)
        self.statistics["filtered_count"] = len(self.records) - len(unique_texts)
        self.statistics["valid_text_count"] = len(unique_texts)
        self.statistics["unique_text_count"] = len(unique_texts)
        self.statistics["duplicate_count"] = duplicate_count
        return self.records, unique_texts

    def _should_translate_table_header_code(self, entity, clean_result) -> bool:
        if not isinstance(entity, DxfTableCellTarget):
            return False
        if entity.row != 0 or clean_result.status != "filtered_code":
            return False
        text = (clean_result.text or "").strip()
        if not 2 <= len(text) <= 24:
            return False
        return bool(re.fullmatch(r"[A-Z][A-Z /&.-]*[A-Z]", text))

    def _refresh_text_statistics(self, unique_texts: list[str]):
        pending_statuses = {"pending", "filtered_duplicate"}
        self.statistics["filtered_count"] = sum(
            1 for record in self.records if record["status"] not in pending_statuses
        )
        self.statistics["valid_text_count"] = len(unique_texts)
        self.statistics["unique_text_count"] = len(unique_texts)

    def _is_ai_keep_decision(self, decision: str | None) -> bool:
        normalized = (decision or "").strip().upper()
        if not normalized:
            return True
        first_token = normalized.replace('"', "").replace("'", "").split()[0]
        return first_token == "KEEP"

    def _mark_ai_filtered_records(self, skipped_texts: set[str]):
        if not skipped_texts:
            return
        for record in self.records:
            if record["status"] not in {"pending", "filtered_duplicate"}:
                continue
            if record.get("cleaned_text") not in skipped_texts:
                continue
            record["status"] = "filtered_ai"
            record["remark"] = "Skipped by AI text filter."

    def _ai_filter_protected_texts(self, unique_texts: list[str]) -> set[str]:
        unique_set = set(unique_texts)
        return {
            record["cleaned_text"]
            for record in self.records
            if record["status"] in {"pending", "filtered_duplicate"}
            and record.get("entity_type") == "ACAD_TABLE_CELL"
            and record.get("table_row") == 0
            and record.get("cleaned_text") in unique_set
        }

    def _filter_unique_texts_with_ai(self, unique_texts: list[str]) -> list[str]:
        if not unique_texts or not self.ai_filter_enable or not self.ai_filter_agent or self.skip_translate:
            return unique_texts
        protected_texts = self._ai_filter_protected_texts(unique_texts)
        ai_texts = [text for text in unique_texts if text not in protected_texts]
        if not ai_texts:
            return unique_texts
        try:
            decisions = self.ai_filter_agent.send_segments(ai_texts, self.chunk_size)
        except Exception as exc:
            self.logger.warning("DXF AI text filter failed; continuing without AI filtering: %s", exc)
            return unique_texts

        kept_texts = [text for text in unique_texts if text in protected_texts]
        skipped_texts = set()
        for text, decision in zip(ai_texts, decisions):
            if self._is_ai_keep_decision(decision):
                kept_texts.append(text)
            else:
                skipped_texts.add(text)
        if len(decisions) < len(ai_texts):
            kept_texts.extend(ai_texts[len(decisions):])

        self._mark_ai_filtered_records(skipped_texts)
        ordered_kept_texts = [text for text in unique_texts if text in set(kept_texts)]
        self._refresh_text_statistics(ordered_kept_texts)
        return ordered_kept_texts

    async def _filter_unique_texts_with_ai_async(self, unique_texts: list[str]) -> list[str]:
        if not unique_texts or not self.ai_filter_enable or not self.ai_filter_agent or self.skip_translate:
            return unique_texts
        protected_texts = self._ai_filter_protected_texts(unique_texts)
        ai_texts = [text for text in unique_texts if text not in protected_texts]
        if not ai_texts:
            return unique_texts
        try:
            decisions = await self.ai_filter_agent.send_segments_async(ai_texts, self.chunk_size)
        except Exception as exc:
            self.logger.warning("DXF AI text filter failed; continuing without AI filtering: %s", exc)
            return unique_texts

        kept_texts = [text for text in unique_texts if text in protected_texts]
        skipped_texts = set()
        for text, decision in zip(ai_texts, decisions):
            if self._is_ai_keep_decision(decision):
                kept_texts.append(text)
            else:
                skipped_texts.add(text)
        if len(decisions) < len(ai_texts):
            kept_texts.extend(ai_texts[len(decisions):])

        self._mark_ai_filtered_records(skipped_texts)
        ordered_kept_texts = [text for text in unique_texts if text in set(kept_texts)]
        self._refresh_text_statistics(ordered_kept_texts)
        return ordered_kept_texts

    def _build_entity_handle_map(self, dxf_doc) -> dict[str, object]:
        return {
            self._entity_key(entity): entity
            for _, entity in self._iter_text_entities(dxf_doc)
            if self._entity_key(entity)
        }

    def _translate_unique_texts(self, unique_texts: list[str]) -> dict[str, str]:
        if not unique_texts:
            return {}
        if self.skip_translate:
            return {text: text for text in unique_texts}

        if self.glossary_agent:
            glossary_dict_gen = self.glossary_agent.send_segments(unique_texts, self.chunk_size)
            if self.glossary:
                self.glossary.update(glossary_dict_gen)
            if self.translate_agent and self.glossary:
                self.translate_agent.update_glossary_dict(self.glossary.glossary_dict)

        translated_texts = self.translate_agent.send_segments(unique_texts, self.chunk_size) if self.translate_agent else unique_texts
        return dict(zip(unique_texts, translated_texts))

    async def _translate_unique_texts_async(self, unique_texts: list[str]) -> dict[str, str]:
        if not unique_texts:
            return {}
        if self.skip_translate:
            return {text: text for text in unique_texts}

        if self.glossary_agent:
            glossary_dict_gen = await self.glossary_agent.send_segments_async(unique_texts, self.chunk_size)
            if self.glossary:
                self.glossary.update(glossary_dict_gen)
            if self.translate_agent and self.glossary:
                self.translate_agent.update_glossary_dict(self.glossary.glossary_dict)

        translated_texts = await self.translate_agent.send_segments_async(unique_texts, self.chunk_size) if self.translate_agent else unique_texts
        return dict(zip(unique_texts, translated_texts))

    def _apply_translations(self, dxf_doc, translation_map: dict[str, str]):
        entity_by_handle = (
            self._entity_by_handle
            if self._entity_doc_id == id(dxf_doc)
            else self._build_entity_handle_map(dxf_doc)
        )
        for record in self.records:
            if record["status"] not in {"pending", "filtered_duplicate"}:
                continue
            entity = entity_by_handle.get(record.get("entity_handle", ""))
            if entity is None:
                record["status"] = "writeback_failed"
                record["remark"] = "DXF entity handle not found."
                self.statistics["writeback_failed_count"] += 1
                continue
            is_duplicate = record["status"] == "filtered_duplicate"
            cleaned_text = record["cleaned_text"]
            translated_text = translation_map.get(cleaned_text)
            if not translated_text:
                record["status"] = "translate_failed"
                record["remark"] = "No translated text returned."
                self.statistics["translate_failed_count"] += 1
                continue
            output_text = self._compose_text(record["original_text"], translated_text)
            try:
                self.layout_adjuster.adjust(entity, record["original_text"], output_text)
                style_name = (
                    self._ensure_unicode_style(dxf_doc, output_text)
                    if self._has_non_ascii(output_text) and not isinstance(entity, DxfTableCellTarget)
                    else None
                )
                written_text = self._set_text(entity, output_text, style_name=style_name)
                record["translated_text"] = translated_text
                if entity.dxftype() == "MTEXT" or isinstance(entity, DxfMLeaderTextTarget):
                    record["mtext_rebuilt_text"] = written_text
                record["status"] = "translated_duplicate" if is_duplicate else "translated"
                self.statistics["translated_count"] += 1
                self.statistics["writeback_success_count"] += 1
            except Exception as exc:
                record["translated_text"] = translated_text
                record["status"] = "writeback_failed"
                record["remark"] = str(exc)
                self.statistics["writeback_failed_count"] += 1

    def _translate_document(self, document: Document, translated_texts_map: dict[str, str]) -> Document:
        dxf_doc = self._load_dxf(document)
        self._apply_translations(dxf_doc, translated_texts_map)
        document.content = self._dump_dxf(dxf_doc)
        return document

    def translate(self, document: Document):
        dxf_doc = self._load_dxf(document)
        _, unique_texts = self._extract_records(dxf_doc)
        unique_texts = self._filter_unique_texts_with_ai(unique_texts)
        if not unique_texts:
            self.logger.info("No translatable TEXT/MTEXT/ATTRIB/ACAD_TABLE/MLEADER content found in DXF.")
            document.content = self._dump_dxf(dxf_doc)
            return self

        translation_map = self._translate_unique_texts(unique_texts)
        self._apply_translations(dxf_doc, translation_map)
        document.content = self._dump_dxf(dxf_doc)
        return self

    async def translate_async(self, document: Document):
        dxf_doc = await asyncio.to_thread(self._load_dxf, document)
        _, unique_texts = self._extract_records(dxf_doc)
        unique_texts = await self._filter_unique_texts_with_ai_async(unique_texts)
        if not unique_texts:
            self.logger.info("No translatable TEXT/MTEXT/ATTRIB/ACAD_TABLE/MLEADER content found in DXF.")
            document.content = await asyncio.to_thread(self._dump_dxf, dxf_doc)
            return self

        translation_map = await self._translate_unique_texts_async(unique_texts)
        await asyncio.to_thread(self._apply_translations, dxf_doc, translation_map)
        document.content = await asyncio.to_thread(self._dump_dxf, dxf_doc)
        return self

    def _terms_csv_document(
        self,
        stem: str | None = None,
        *,
        translated_only: bool = False,
    ) -> Document:
        output = io.StringIO()
        fieldnames = [
            "src",
            "dst",
            "id",
            "entity_handle",
            "entity_type",
            "layout_name",
            "original_text",
            "cleaned_text",
            "translated_text",
            "mtext_rebuilt_text",
            "block_name",
            "attrib_tag",
            "table_row",
            "table_col",
            "status",
            "remark",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in self.records:
            if translated_only and record.get("status") not in {"translated", "translated_duplicate"}:
                continue
            row = {
                **record,
                "src": record.get("cleaned_text") or record.get("original_text", ""),
                "dst": record.get("translated_text", ""),
            }
            writer.writerow(row)
        prefix = "translated_terms_only" if translated_only else "translated_terms"
        name = f"{prefix}_{stem or 'dxf'}"
        return Document.from_bytes(output.getvalue().encode("utf-8-sig"), ".csv", name)

    def get_terms_csv_document(self, stem: str | None = None) -> Document:
        return self._terms_csv_document(stem, translated_only=False)

    def get_translated_terms_csv_document(self, stem: str | None = None) -> Document:
        output = io.StringIO()
        fieldnames = ["src", "dst"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        seen: set[str] = set()
        for record in self.records:
            if record.get("status") != "translated":
                continue
            src = record.get("cleaned_text") or record.get("original_text", "")
            if not src or src in seen:
                continue
            seen.add(src)
            writer.writerow(
                {
                    "src": src,
                    "dst": record.get("translated_text", ""),
                }
            )
        name = f"translated_terms_only_{stem or 'dxf'}"
        return Document.from_bytes(output.getvalue().encode("utf-8-sig"), ".csv", name)
