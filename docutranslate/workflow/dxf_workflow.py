# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from docutranslate.exporter.base import ExporterConfig
from docutranslate.exporter.dxf.dxf2dxf_exporter import Dxf2DxfExporter
from docutranslate.glossary.glossary import Glossary
from docutranslate.ir.document import Document
from docutranslate.translator.ai_translator.dxf_translator import DxfTranslator, DxfTranslatorConfig
from docutranslate.workflow.base import Workflow, WorkflowConfig
from docutranslate.workflow.interfaces import DxfExportable


@dataclass(kw_only=True)
class DxfWorkflowConfig(WorkflowConfig):
    translator_config: DxfTranslatorConfig


class DxfWorkflow(Workflow[DxfWorkflowConfig, Document, Document], DxfExportable[ExporterConfig]):
    def __init__(self, config: DxfWorkflowConfig):
        super().__init__(config=config)
        self._translator: DxfTranslator | None = None
        if config.logger and self.config.translator_config:
            self.config.translator_config.logger = config.logger

    def _pre_translate(self, document_original: Document):
        document = document_original.copy()
        translator = DxfTranslator(self.config.translator_config)
        return document, translator

    def translate(self) -> Self:
        self.progress_tracker.update(percent=10, message="Preparing DXF translation...")
        document, translator = self._pre_translate(self.document_original)
        self._translator = translator
        translator.translate(document)

        if translator.glossary.glossary_dict:
            self.progress_tracker.update(percent=95, message="Exporting glossary...")
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary.glossary_dict))
        self.attachment.add_document("dxf_terms", translator.get_terms_csv_document(document.stem))
        self.attachment.add_document("dxf_translated_terms", translator.get_translated_terms_csv_document(document.stem))

        self.progress_tracker.update(percent=100, message="DXF translation completed.")
        self.document_translated = document
        return self

    async def translate_async(self) -> Self:
        self.progress_tracker.update(percent=10, message="Preparing DXF translation...")
        document, translator = self._pre_translate(self.document_original)
        self._translator = translator
        await translator.translate_async(document)

        if translator.glossary.glossary_dict:
            self.progress_tracker.update(percent=95, message="Exporting glossary...")
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary.glossary_dict))
        self.attachment.add_document("dxf_terms", translator.get_terms_csv_document(document.stem))
        self.attachment.add_document("dxf_translated_terms", translator.get_translated_terms_csv_document(document.stem))

        self.progress_tracker.update(percent=100, message="DXF translation completed.")
        self.document_translated = document
        return self

    def get_statistics(self) -> dict:
        if self._translator:
            stats = self._translator.get_statistics()
            stats["dxf"] = self._translator.statistics
            return stats
        return {}

    def export_to_dxf(self, _: ExporterConfig | None = None) -> bytes:
        docu = self._export(Dxf2DxfExporter())
        return docu.content

    def save_as_dxf(
        self,
        name: str = None,
        output_dir: Path | str = "./output",
        _: ExporterConfig | None = None,
    ) -> Self:
        self._save(exporter=Dxf2DxfExporter(), name=name, output_dir=output_dir)
        return self

    def save_terms_csv(self, name: str = None, output_dir: Path | str = "./output") -> Self:
        if self._translator is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        docu = self._translator.get_terms_csv_document(
            self.document_translated.stem if self.document_translated else None
        )
        name = name or docu.name
        output_path = Path(output_dir) / Path(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(docu.content)
        return self

    def save_translated_terms_csv(self, name: str = None, output_dir: Path | str = "./output") -> Self:
        if self._translator is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        docu = self._translator.get_translated_terms_csv_document(
            self.document_translated.stem if self.document_translated else None
        )
        name = name or docu.name
        output_path = Path(output_dir) / Path(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(docu.content)
        return self
