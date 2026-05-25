# Engineer Branding Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the delivered application to DocuTranslate for engineer, update homepage/tutorial copy for DXF/DWG engineering workflows, and package the Windows exe as version 1.0.0.

**Architecture:** Keep the original DocuTranslate backend, translator, workflow, and API logic unchanged. Modify only frontend/i18n copy, static assets generated from the frontend, and PyInstaller output naming.

**Tech Stack:** Vue frontend, JSON i18n files, Vite build, FastAPI static hosting, PyInstaller.

---

### Task 1: Update Branding And Homepage Copy

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/public/i18n/zh.json`
- Modify: `frontend/public/i18n/en.json`
- Modify: `frontend/public/i18n/vi.json`
- Modify: `docutranslate/app.py`

- [ ] Set browser title and page title to `DocuTranslate for engineer`.
- [ ] Replace the homepage GitHub/QQ/version text with the engineering edition note and `version:v1.0.0`.
- [ ] Keep the original package version untouched.

### Task 2: Update Tutorial Copy

**Files:**
- Modify: `frontend/public/i18n/zh.json`
- Modify: `frontend/public/i18n/en.json`
- Modify: `frontend/public/i18n/vi.json`

- [ ] Add DXF workflow explanation to the tutorial workflow list.
- [ ] Add DWG workflow explanation, including ODA File Converter requirement.
- [ ] Keep wording short enough for the existing modal layout.

### Task 3: Update Packaging Name

**Files:**
- Modify: `full.spec`

- [ ] Change PyInstaller output name to `DocuTranslate_for_engineer-1.0.0-win`.
- [ ] Keep executable entrypoint, bundled static files, and icon unchanged.

### Task 4: Build And Verify

**Commands:**
- `npm.cmd run build -- --outDir dist-engineer --emptyOutDir true`
- Copy built `index.html`, assets, and i18n into `docutranslate/static`.
- `.\.venv\Scripts\python.exe -m pytest tests\test_dxf tests\test_dwg -q`
- `.\.venv\Scripts\python.exe -m PyInstaller full.spec --noconfirm --clean`
- Start the exe on a test port and verify `/service/meta` returns HTTP 200.
