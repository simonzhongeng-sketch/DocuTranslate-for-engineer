# DocuTranslate for engineer 技术路线与功能说明

`DocuTranslate for engineer` 基于开源项目 [DocuTranslate](https://github.com/xunbu/docutranslate) 二次开发，核心目标是在保留原项目多 AI 平台翻译、Web UI、RESTful API、术语表、异步并发翻译、多格式工作流等能力的基础上，扩展工程图纸文件翻译能力。

本项目没有重写原有翻译模型、AI 调用方式、并发机制、配置方式和 Web UI，而是新增 DXF/DWG 工程图纸翻译工作流，让工程文件与 docx、xlsx、txt、pptx 等文件一样进入统一翻译流程。

如果本项目对你有帮助，也欢迎前往源项目 [xunbu/docutranslate](https://github.com/xunbu/docutranslate) 点 Star 支持原作者。

当前工程版展示版本为 `v1.0.0`。

## 1. 总体技术路线

整体路线如下：

1. Web UI/API 接收上传文件和翻译配置。
2. 根据文件类型选择工作流。
3. DXF 文件进入 DXF Workflow。
4. DWG 文件先通过 ODA File Converter 转为 DXF，再复用 DXF Workflow。
5. DXF Workflow 使用 `ezdxf` 读取图纸文本对象。
6. 执行文本清洗、文本筛选、去重和可选 AI 文本筛选。
7. 复用 DocuTranslate 原有 Translator、术语表、并发、重试、Prompt、目标语言等配置执行翻译。
8. 将译文回填到 DXF 对象。
9. DWG 工作流将翻译后的 DXF 再转换为目标 DWG 版本。
10. 输出翻译后的 DXF/DWG、完整术语 CSV 和仅包含已翻译内容的 CSV。

## 2. 原项目复用范围

继续复用 DocuTranslate 原有能力：

- AI 平台配置：`base_url`、`api_key`、`model_id` 等。
- 翻译配置：目标语言、并发数、温度、超时、重试、分块大小、自定义 Prompt。
- 术语表机制：上传术语表、自动生成术语表、术语替换与约束。
- Web UI：沿用原前端页面和任务卡片交互。
- API：沿用原文件上传、状态查询、日志、下载和附件机制。
- 异步任务：沿用原后台任务处理和进度日志。
- 输出机制：沿用原下载文件和附件下载方式。

新增 DXF/DWG 能力只作为工作流扩展，不另起一套翻译框架。

## 3. DXF Workflow

DXF 使用 `ezdxf` 直接读取和回写，不依赖 AutoCAD。

核心流程：

1. 读取 DXF 文件。
2. 遍历 modelspace、paperspace/layouts、blocks。
3. 提取受支持实体中的文本。
4. 生成统一文本记录。
5. 对文本进行清洗、筛选、去重。
6. 调用原项目翻译器批量翻译。
7. 将译文回填到原实体。
8. 保存翻译后的 DXF。
9. 导出 CSV 术语文件。

主要模块：

- `docutranslate/workflow/dxf_workflow.py`
- `docutranslate/workflow/dxf_text_cleaner.py`
- `docutranslate/workflow/dxf_layout.py`
- `docutranslate/workflow/dxf_mtext.py`
- `docutranslate/translator/ai_translator/dxf_translator.py`
- `docutranslate/exporter/dxf/dxf2dxf_exporter.py`

## 4. DXF 支持对象

当前支持：

- `TEXT`
- `MTEXT`
- `ATTRIB`
- 图块内文本
- 表格单元格文本
- 引线文字对象

当前不处理或不重点优化：

- DWG 原生二进制解析。
- 复杂 CAD 几何结构重排。
- 非文本类图元翻译。
- 表格复杂排版重算。
- 依赖 AutoCAD 的专有对象。

## 5. 文本清洗与筛选

DXF/DWG 文本筛选通过工作流配置控制。

页面提供以下选项：

- 翻译前清洗文本。
- 启用文本筛选。
- AI 文本筛选。
- 自定义 AI 筛选 Prompt。
- DWG ODA 路径和转换超时。
- DWG 输出版本。

清洗逻辑：

- 去除开头和末尾空白。
- 合并多余空格。
- 保留必要换行。
- 规范部分全角字符。
- 将清洗后的文本作为筛选和去重依据。

筛选逻辑：

- 过滤空文本。
- 过滤纯数字。
- 过滤纯符号。
- 过滤工程位号、设备编号、端子号、型号、规格参数等非译内容。
- 过滤已经是目标语言的内容。
- 可按源语言过滤非源语言内容。

典型过滤示例：

- `L0SW01`
- `H100*W35`
- `MCU`
- `PDU-IN-V1+`
- `TB54(24VDC-)`
- `PSU11- +`
- `5.4A,50-60Hz`
- `1:1`
- `(CN032)`

## 6. 去重策略

翻译前对清洗后的文本统一去重：

1. 相同 `cleaned_text` 只进入翻译模型一次。
2. 建立 `cleaned_text -> translated_text` 映射。
3. 回填时将同一译文写回所有对应实体。
4. CSV 仍保留每个实体的明细记录，便于人工核对。

这样可以减少大图纸和批量文件中的重复翻译量，提高翻译效率。

## 7. AI 文本筛选

AI 文本筛选是 DXF/DWG 工作流中的可选步骤，默认开启。

作用：

- 在正式翻译前，让当前配置的 AI 模型判断每段文本是否需要翻译。
- 模型只输出 `KEEP` 或 `SKIP`。
- `KEEP` 的文本进入翻译。
- `SKIP` 的文本保持原文。

默认策略偏保守：

- 不确定时倾向 `KEEP`。
- 表头、列名、行标签、标题、说明性文字优先保留翻译。
- 纯数字、符号、工程位号、设备编号、参数值、单位、电气编码、已是目标语言的内容优先跳过。

AI 筛选 Prompt 可在页面中修改。

## 8. MTEXT 处理

MTEXT 不是普通纯文本，内部可能包含 DXF 控制码和格式信息。

处理策略：

- 提取时优先读取可翻译纯文本。
- 回填时按 MTEXT 内容格式重新组装。
- 尽量保留原实体宽度、高度、旋转角度、插入点、附着方式、样式、图层等属性。
- 避免直接把普通字符串写入导致控制码丢失。

由于不同 CAD 软件对 MTEXT 自动重排刷新机制不同，当前策略以保留结构和可显示性为优先，不进行复杂几何重排。

## 9. 表格翻译

表格文本按单元格提取和回写。

处理策略：

- 单纯翻译表格文本。
- 不做复杂表格排版重算。
- 表头、列名、行标签默认倾向翻译。
- 对明显工程编码、参数值、已经是目标语言的内容继续筛选。

目标是保证表格文本能回写并保持图纸结构不被破坏。

## 10. DWG Workflow

DWG 不直接解析，而是依赖 ODA File Converter 转换：

1. 自动识别 ODA File Converter 安装路径。
2. 允许用户在 DWG 选项中手动选择 `ODAFileConverter.exe`。
3. 将源 DWG 转换为临时 DXF。
4. 调用 DXF Workflow 完成翻译。
5. 将翻译后的 DXF 转换为目标 DWG 版本。
6. 输出翻译后的 DWG 文件。

DWG 输出版本通过页面下拉框选择，默认 `ACAD2007`。

主要模块：

- `docutranslate/workflow/dwg_workflow.py`
- `docutranslate/workflow/oda_converter.py`

外部依赖：

- ODA File Converter。
- 下载地址由页面提示。
- 该软件不内置在 exe 中。

## 11. 输出文件

DXF/DWG 翻译完成后输出：

- 翻译后的 `.dxf` 文件。
- 翻译后的 `.dwg` 文件。
- 完整术语 CSV。
- 仅包含实际翻译内容的 CSV。

CSV 用途：

- 人工复核原文和译文。
- 检查被过滤文本。
- 追踪实体类型、句段状态和回填结果。
- 后期作为术语表或审校依据。

常见 CSV 字段：

- `id`
- `entity_handle`
- `entity_type`
- `layout_name`
- `original_text`
- `cleaned_text`
- `translated_text`
- `status`
- `remark`
- MTEXT 重新组装后的内容字段。

## 12. Web UI 与 API 接入

Web UI 扩展点：

- 文件上传支持 `.dxf` 和 `.dwg`。
- 工作流选择中增加 DXF 图纸翻译和 DWG 图纸翻译。
- DXF/DWG 工作流显示专用配置项。
- DWG 工作流显示 ODA 路径选择、转换超时和输出版本。
- 任务完成后支持下载翻译后的图纸和 CSV 附件。

API 仍复用原 `/service/translate/file`、状态查询、日志查询、下载和附件接口。

## 13. 打包路线

Windows exe 使用 PyInstaller 打包。

打包入口：

- `docutranslate/app.py`

打包配置：

- `full.spec`

工程版输出：

- `dist/DocuTranslate_for_engineer-1.0.0-win.exe`

前端构建流程：

1. 在 `frontend` 目录执行 Vite build。
2. 将构建后的 `index.html`、`assets`、`i18n` 同步到 `docutranslate/static`。
3. PyInstaller 收集 `docutranslate/static` 和 `docutranslate/template`。
4. 生成单文件 Windows exe。

## 14. 运行方式

开发环境运行：

```powershell
.\.venv\Scripts\python.exe -m docutranslate.cli -i
```

或直接运行应用入口：

```powershell
.\.venv\Scripts\python.exe docutranslate\app.py
```

打包后运行：

```powershell
.\dist\DocuTranslate_for_engineer-1.0.0-win.exe
```

默认访问：

```text
http://127.0.0.1:8010/
```

如果端口被占用，程序会自动选择后续可用端口。

## 15. 验证范围

当前重点验证：

- DXF 文件读取。
- TEXT 提取和回填。
- MTEXT 提取、组装和回填。
- ATTRIB 和图块文本处理。
- 表格文本处理。
- 引线文字处理。
- 文本清洗和筛选。
- 去重翻译。
- CSV 导出。
- DWG ODA 转换路径识别。
- DWG 转 DXF 后复用 DXF Workflow。
- 前端工程版文案。
- Windows exe 启动。

## 16. 当前限制

- DWG 翻译依赖 ODA File Converter，系统未安装或路径错误时无法转换。
- 不进行 DWG 原生二进制解析。
- 表格只保证文本翻译和回写，不做复杂排版重算。
- MTEXT 尽量保留结构和显示效果，但不同 CAD 软件可能存在刷新和自动重排差异。
- 不翻译非文本图形对象。
- 不保证所有专有 CAD 对象都可被 `ezdxf` 完整解析。
