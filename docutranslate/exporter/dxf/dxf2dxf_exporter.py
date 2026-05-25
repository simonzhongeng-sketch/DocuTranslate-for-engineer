# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0
from docutranslate.exporter.dxf.base import DxfExporter
from docutranslate.ir.document import Document


class Dxf2DxfExporter(DxfExporter):
    def export(self, document: Document) -> Document:
        return document.copy()
