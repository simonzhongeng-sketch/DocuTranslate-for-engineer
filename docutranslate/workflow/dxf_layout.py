# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass


@dataclass(kw_only=True)
class DxfLayoutConfig:
    min_scale: float = 0.65
    text_length_threshold: float = 1.2
    mtext_length_threshold: float = 1.5


class DxfLayoutAdjuster:
    def __init__(self, config: DxfLayoutConfig | None = None):
        self.config = config or DxfLayoutConfig()

    def adjust(self, entity, original_text: str, translated_text: str):
        return

    def _length_ratio(self, original_text: str, translated_text: str) -> float:
        original_len = max(self._visual_length(original_text), 1.0)
        translated_len = max(self._visual_length(translated_text), 1.0)
        return translated_len / original_len

    def _visual_length(self, text: str) -> float:
        total = 0.0
        for ch in text:
            if ch in "\r\n":
                continue
            total += 1.0 if ord(ch) < 128 else 1.6
        return total

    def _scale_for_ratio(self, ratio: float, threshold: float) -> float:
        if ratio <= threshold:
            return 1.0
        return max(self.config.min_scale, threshold / ratio)

    def _adjust_text(self, entity, ratio: float):
        scale = self._scale_for_ratio(ratio, self.config.text_length_threshold)
        if scale >= 1.0 or not hasattr(entity.dxf, "height"):
            return
        entity.dxf.height = max(entity.dxf.height * scale, entity.dxf.height * self.config.min_scale)

    def _adjust_mtext(self, entity, ratio: float):
        scale = self._scale_for_ratio(ratio, self.config.mtext_length_threshold)
        if scale >= 1.0:
            return
        if hasattr(entity.dxf, "char_height") and entity.dxf.char_height:
            entity.dxf.char_height = max(entity.dxf.char_height * scale, entity.dxf.char_height * self.config.min_scale)
