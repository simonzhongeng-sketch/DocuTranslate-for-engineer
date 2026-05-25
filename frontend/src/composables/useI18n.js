import { ref } from 'vue';

export function useI18n() {
    const currentLang = ref(localStorage.getItem('ui_language') || 'zh');
    const i18nData = ref({});

    const t = (k, params) => {
        let v = i18nData.value[k] || k;
        if (params) {
            for (const [key, val] of Object.entries(params)) {
                v = v.replace(new RegExp(`\\{${key}\\}`, 'g'), String(val));
            }
        }
        return v;
    };

    const setLanguage = async (l) => {
        currentLang.value = l;
        localStorage.setItem('ui_language', l);
        document.documentElement.lang = l === 'zh' ? 'zh-CN' : (l === 'vi' ? 'vi' : 'en');
        // Reload i18n data
        try {
            const res = await fetch(`/static/i18n/${l}.json?v=${Date.now()}`, { cache: 'no-store' });
            i18nData.value = await res.json();
            document.title = i18nData.value.pageTitle || 'DocuTranslate for engineer';
        } catch (e) {
            console.error('Failed to load i18n:', e);
        }
    };

    const loadI18n = async () => {
        try {
            const lang = currentLang.value || 'zh';
            const res = await fetch(`/static/i18n/${lang}.json?v=${Date.now()}`, { cache: 'no-store' });
            i18nData.value = await res.json();
            document.title = i18nData.value.pageTitle || 'DocuTranslate for engineer';
        } catch (e) {
            // Fallback defaults
            i18nData.value = {
                pageTitle: "DocuTranslate for engineer",
                appName: "DocuTranslate for engineer",
                engineerIntro: "本应用基于DocuTranslate开发而来，增加了对工程文件(DXF\\DWG)的支持，",
                engineerVersion: "version:v1.0.0",
                tutorialBtn: "教程",
                projectContributeBtn: "项目协作",
                workflowTitle: "选择工作流",
                autoWorkflowLabel: "自动选择工作流",
                workflowOptionPptx: "PPTX 演示文稿",
                workflowOptionDxf: "DXF 图纸",
                pptxSettingsTitleText: "PPTX 设置",
                dxfSettingsTitleText: "DXF 设置",
                insertModeHelpDxf: "选择如何将译文写入 TEXT 和 MTEXT 实体。",
                mineruDeployServerUrlLabel: "Server URL",
                mineruDeployLangListLabel: "语言列表 (Pipeline模式)",
                mineruDeployServerUrlPlaceholder: "http://127.0.0.1:30000",
                mineruDeployParseMethodLabel: "解析方法 (Parse Method)",
                mineruDeployTableEnableLabel: "表格识别 (Table Recognition)"
            };
            document.title = i18nData.value.pageTitle;
        }
    };

    return {
        currentLang,
        i18nData,
        t,
        setLanguage,
        loadI18n
    };
}
