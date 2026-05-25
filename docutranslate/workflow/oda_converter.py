# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
import os
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"

ODA_DEFAULT_PATHS = (
    Path(r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"),
    Path(r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe"),
)
ODA_DEFAULT_ROOTS = (
    Path(r"C:\Program Files\ODA"),
    Path(r"C:\Program Files (x86)\ODA"),
)


@dataclass(kw_only=True)
class OdaFileConverterConfig:
    executable_path: str | None = None
    timeout: int = 300


class OdaFileConverter:
    def __init__(self, config: OdaFileConverterConfig | None = None):
        self.config = config or OdaFileConverterConfig()
        self.executable_path = self.resolve_executable(self.config.executable_path)

    @classmethod
    def resolve_executable(cls, configured_path: str | None = None) -> Path:
        configured_path = cls._clean_executable_path(configured_path)
        if configured_path:
            path = Path(configured_path).expanduser()
            if path.is_file():
                return path
            raise RuntimeError(cls._not_found_message(configured_path))

        path_from_env = cls._clean_executable_path(os.environ.get("ODA_FILE_CONVERTER"))
        if path_from_env and Path(path_from_env).is_file():
            return Path(path_from_env)

        path_from_path = shutil.which("ODAFileConverter.exe") or shutil.which("ODAFileConverter")
        if path_from_path:
            return Path(path_from_path)

        for candidate in ODA_DEFAULT_PATHS:
            if candidate.is_file():
                return candidate

        for root in ODA_DEFAULT_ROOTS:
            for candidate in sorted(root.glob("ODAFileConverter*/ODAFileConverter.exe"), reverse=True):
                if candidate.is_file():
                    return candidate

        raise RuntimeError(cls._not_found_message())

    @staticmethod
    def _clean_executable_path(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = "".join(ch for ch in str(value) if unicodedata.category(ch) != "Cf")
        cleaned = cleaned.strip().strip("\"'")
        return cleaned or None

    @staticmethod
    def _not_found_message(configured_path: str | None = None) -> str:
        detail = f" configured path was '{configured_path}'." if configured_path else ""
        return (
            "ODA File Converter was not found."
            f"{detail} Install it from "
            f"{ODA_DOWNLOAD_URL} or set the ODA File Converter executable path manually."
        )

    def convert_file(self, source: Path, output_dir: Path, output_version: str, output_type: str) -> Path:
        source = Path(source)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        input_dir = source.parent
        output_type = output_type.upper()
        before = {
            path.resolve()
            for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() == f".{output_type.lower()}"
        }

        command = [
            str(self.executable_path),
            str(input_dir),
            str(output_dir),
            output_version,
            output_type,
            "0",
            "1",
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"ODA File Converter timed out after {self.config.timeout} seconds while converting to {output_type}."
            ) from exc

        if result.returncode != 0:
            output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
            raise RuntimeError(f"ODA File Converter failed while converting to {output_type}: {output}")

        converted = self._find_converted_file(source, output_dir, output_type.lower(), before)
        if converted is None:
            raise RuntimeError(f"ODA File Converter did not produce a .{output_type.lower()} file for {source.name}.")
        return converted

    def _find_converted_file(self, source: Path, output_dir: Path, suffix: str, before: set[Path]) -> Path | None:
        for expected in (output_dir / f"{source.stem}.{suffix}", output_dir / f"{source.stem}.{suffix.upper()}"):
            if expected.is_file():
                return expected
        candidates = [
            path for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() == f".{suffix}" and path.resolve() not in before
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)
