# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def wrap_mtext_plain_text(text: str, width: float, char_height: float) -> str:
    if width <= 0 or char_height <= 0:
        return text
    max_width = max(width / char_height, 4.0)
    wrapped_lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        wrapped_lines.extend(_wrap_line_by_visual_width(line, max_width))
    return "\n".join(wrapped_lines)


def rebuild_mtext_content(original_content: str, translated_text: str, encode_text) -> str:
    """Rebuild MTEXT content by preserving inline commands and replacing visible text.

    MTEXT content is not plain text: it can contain paragraph separators, formatting
    groups, color/font/height commands, and escaped characters. This conservative
    rebuilder keeps the original MTEXT command skeleton and injects translated
    plain text into the visible text slots.
    """

    paragraphs = _split_mtext_paragraphs(original_content)
    translated_lines = translated_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rebuilt: list[str] = []
    line_index = 0

    for paragraph, separator in paragraphs:
        line = translated_lines[line_index] if line_index < len(translated_lines) else ""
        rebuilt.append(_replace_visible_text(paragraph, encode_text(line)))
        if separator:
            rebuilt.append(separator)
        line_index += 1

    while line_index < len(translated_lines):
        if rebuilt and not (rebuilt[-1].upper() == r"\P"):
            rebuilt.append(r"\P")
        rebuilt.append(encode_text(translated_lines[line_index]))
        line_index += 1

    return "".join(rebuilt)


def _wrap_line_by_visual_width(line: str, max_width: float) -> list[str]:
    if not line:
        return [line]

    result: list[str] = []
    current: list[str] = []
    current_width = 0.0
    last_break_index = -1

    for char in line:
        char_width = _char_visual_width(char)
        if current and current_width + char_width > max_width:
            if last_break_index > 0:
                result.append("".join(current[:last_break_index]).rstrip())
                current = current[last_break_index:]
                while current and current[0].isspace():
                    current.pop(0)
                current_width = sum(_char_visual_width(item) for item in current)
                last_break_index = _last_break_index(current)
            else:
                result.append("".join(current).rstrip())
                current = []
                current_width = 0.0
                last_break_index = -1
        current.append(char)
        current_width += char_width
        if char.isspace() or char in ",.;:，。；：、/\\-":
            last_break_index = len(current)

    if current:
        result.append("".join(current).rstrip())
    return result or [""]


def _char_visual_width(char: str) -> float:
    if char.isspace():
        return 0.35
    if ord(char) < 128:
        return 0.55
    return 1.0


def _last_break_index(chars: list[str]) -> int:
    for index in range(len(chars), 0, -1):
        char = chars[index - 1]
        if char.isspace() or char in ",.;:，。；：、/\\-":
            return index
    return -1


def _split_mtext_paragraphs(content: str) -> list[tuple[str, str]]:
    paragraphs: list[tuple[str, str]] = []
    start = 0
    index = 0
    while index < len(content):
        if content[index] == "\\" and index + 1 < len(content):
            command = content[index + 1]
            if command.upper() == "P":
                paragraphs.append((content[start:index], content[index : index + 2]))
                index += 2
                start = index
                continue
            index = _skip_mtext_command(content, index)
            continue
        index += 1
    paragraphs.append((content[start:], ""))
    return paragraphs


def _replace_visible_text(content: str, replacement: str) -> str:
    result: list[str] = []
    inserted = False
    index = 0
    while index < len(content):
        char = content[index]
        if char == "\\" and index + 1 < len(content):
            command = content[index + 1]
            if command in "\\{}":
                if not inserted:
                    result.append(replacement)
                    inserted = True
                index += 2
                continue
            if command == "~":
                if not inserted:
                    result.append(replacement)
                    inserted = True
                index += 2
                continue
            if command.upper() == "S":
                end = content.find(";", index + 2)
                index = len(content) if end == -1 else end + 1
                continue
            next_index = _skip_mtext_command(content, index)
            result.append(content[index:next_index])
            index = next_index
            continue
        if char in "{}":
            result.append(char)
            index += 1
            continue
        if char.isspace():
            if not inserted:
                result.append(replacement)
                inserted = True
            index += 1
            continue
        if not inserted:
            result.append(replacement)
            inserted = True
        index += 1

    if not inserted:
        result.append(replacement)
    return "".join(result)


def _skip_mtext_command(content: str, index: int) -> int:
    if index + 1 >= len(content) or content[index] != "\\":
        return index + 1
    command = content[index + 1]
    if command in "\\{}~":
        return index + 2
    if command.upper() in "PNX":
        return index + 2
    if command.upper() == "S":
        end = content.find(";", index + 2)
        return len(content) if end == -1 else end + 1
    end = content.find(";", index + 2)
    return index + 2 if end == -1 else end + 1
