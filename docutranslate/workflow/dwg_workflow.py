# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from docutranslate.exporter.base import ExporterConfig
from docutranslate.ir.document import Document
from docutranslate.translator.ai_translator.dxf_translator import DxfTranslatorConfig
from docutranslate.workflow.base import Workflow, WorkflowConfig
from docutranslate.workflow.dxf_workflow import DxfWorkflow, DxfWorkflowConfig
from docutranslate.workflow.interfaces import DxfExportable
from docutranslate.workflow.oda_converter import OdaFileConverter, OdaFileConverterConfig


DEFAULT_DWG_OUTPUT_VERSIONS = ("ACAD2007",)


@dataclass(kw_only=True)
class DwgWorkflowConfig(WorkflowConfig):
    translator_config: DxfTranslatorConfig
    oda_path: str | None = None
    oda_timeout: int = 300
    dwg_output_versions: tuple[str, ...] = field(default_factory=lambda: DEFAULT_DWG_OUTPUT_VERSIONS)
    dxf_output_version: str = "ACAD2018"
    converter: object | None = None


class DwgWorkflow(Workflow[DwgWorkflowConfig, Document, Document], DxfExportable[ExporterConfig]):
    def __init__(self, config: DwgWorkflowConfig):
        super().__init__(config=config)
        self._dxf_workflow: DxfWorkflow | None = None
        if config.logger and self.config.translator_config:
            self.config.translator_config.logger = config.logger

    def _get_converter(self):
        if self.config.converter is not None:
            return self.config.converter
        return OdaFileConverter(
            OdaFileConverterConfig(
                executable_path=self.config.oda_path or None,
                timeout=self.config.oda_timeout,
            )
        )

    def translate(self) -> Self:
        self.progress_tracker.update(percent=5, message="Preparing DWG translation...")
        self._translate_sync()
        self.progress_tracker.update(percent=100, message="DWG translation completed.")
        return self

    async def translate_async(self) -> Self:
        self.progress_tracker.update(percent=5, message="Preparing DWG translation...")
        await asyncio.to_thread(self._translate_sync)
        self.progress_tracker.update(percent=100, message="DWG translation completed.")
        return self

    def _translate_sync(self):
        if self.document_original is None:
            raise RuntimeError("Document has not been loaded. Call read_path() or read_bytes() first.")
        converter = self._get_converter()
        with tempfile.TemporaryDirectory(prefix="docutranslate_dwg_") as temp_root:
            temp_dir = Path(temp_root)
            source_dir = temp_dir / "source"
            dxf_dir = temp_dir / "dxf"
            source_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / f"{self.document_original.stem or 'source'}.dwg"
            source_path.write_bytes(self.document_original.content)

            self.progress_tracker.update(percent=10, message="Converting DWG to DXF with ODA File Converter...")
            dxf_path = converter.convert_file(
                source_path,
                dxf_dir,
                self.config.dxf_output_version,
                "DXF",
            )

            self.progress_tracker.update(percent=15, message="Running DXF translation workflow...")
            dxf_workflow = DxfWorkflow(
                DxfWorkflowConfig(
                    translator_config=self.config.translator_config,
                    logger=self.config.logger,
                    progress_tracker=self.progress_tracker,
                )
            )
            dxf_workflow.read_bytes(
                content=dxf_path.read_bytes(),
                stem=self.document_original.stem,
                suffix=".dxf",
            )
            dxf_workflow.translate()

            self._dxf_workflow = dxf_workflow
            self.document_translated = dxf_workflow.document_translated
            attachment = dxf_workflow.get_attachment()
            if attachment:
                self.attachment.attachment_dict.update(attachment.attachment_dict)

    def get_statistics(self) -> dict:
        if self._dxf_workflow:
            stats = self._dxf_workflow.get_statistics()
            stats["dwg"] = {
                "output_versions": list(self.config.dwg_output_versions),
                "oda_timeout": self.config.oda_timeout,
            }
            return stats
        return {}

    def export_to_dxf(self, _: ExporterConfig | None = None) -> bytes:
        if self.document_translated is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        return self.document_translated.content

    def save_as_dxf(
        self,
        name: str = None,
        output_dir: Path | str = "./output",
        _: ExporterConfig | None = None,
    ) -> Self:
        if self.document_translated is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        name = name or self.document_translated.name
        output_path = Path(output_dir) / Path(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.document_translated.content)
        return self

    def export_to_dwg(self, version: str) -> bytes:
        if self.document_translated is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        converter = self._get_converter()
        with tempfile.TemporaryDirectory(prefix="docutranslate_dwg_export_") as temp_root:
            temp_dir = Path(temp_root)
            source_dir = temp_dir / "source"
            output_dir = temp_dir / "dwg"
            source_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / f"{self.document_translated.stem or 'translated'}.dxf"
            source_path.write_bytes(self.document_translated.content)
            dwg_path = converter.convert_file(source_path, output_dir, version, "DWG")
            return dwg_path.read_bytes()

    def save_as_dwg(self, version: str, name: str = None, output_dir: Path | str = "./output") -> Self:
        content = self.export_to_dwg(version)
        output_name = name or f"{self.document_translated.stem or 'translated'}_{version}.dwg"
        output_path = Path(output_dir) / Path(output_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return self
