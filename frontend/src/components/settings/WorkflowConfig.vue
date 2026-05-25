<template>
    <!-- 1. Workflow Configuration (Merged) -->
    <Collapse v-model="isWorkflowConfigOpen">
        <template #header>
            <strong>
                <Heroicon name="Cog6ToothIcon" class="w-5 h-5 inline-block mr-2" />
                <span>{{ t('workflowConfigTitle') }}</span>
            </strong>
        </template>

        <!-- Top: Configure default workflow button -->
        <div class="mb-3">
            <Button variant="outline-primary" @click="openDefaultWorkflowModal">
                <Heroicon name="Cog6ToothIcon" class="w-4 h-4 mr-2" />
                {{ t('openExtWorkflowBtn') }}
            </Button>
        </div>
        <!-- Workflow type selection -->
        <div class="mb-3">
            <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                    v-model="form.workflow_type"
                    @change="saveSetting('translator_last_workflow', form.workflow_type)">
                <option value="markdown_based">{{ t('workflowOptionMarkdown') }}</option>
                <option value="docx">{{ t('workflowOptionDocx') }}</option>
                <option value="xlsx">{{ t('workflowOptionXlsx') }}</option>
                <option value="epub">{{ t('workflowOptionEpub') }}</option>
                <option value="txt">{{ t('workflowOptionTxt') }}</option>
                <option value="pptx">{{ t('workflowOptionPptx') }}</option>
                <option value="dxf">{{ t('workflowOptionDxf') || 'DXF Drawing (.dxf)' }}</option>
                <option value="dwg">{{ t('workflowOptionDwg') || 'DWG Drawing (.dwg)' }}</option>
                <option value="srt">{{ t('workflowOptionSrt') }}</option>
                <option value="ass">{{ t('workflowOptionAss') }}</option>
                <option value="json">{{ t('workflowOptionJson') }}</option>
                <option value="html">{{ t('workflowOptionHtml') }}</option>
            </select>
        </div>
        <hr class="border-gray-200 dark:border-gray-700 my-4">
        <!-- Workflow-specific options -->
        <template v-if="currentWorkflowConfig">
            <!-- Common Insert Mode -->
            <div class="mb-3" v-if="currentWorkflowConfig.hasInsertMode">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('insertModeLabel') }}</label>
                <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                        v-model="workflowParams[form.workflow_type].insert_mode"
                        @change="saveWorkflowParam('insert_mode')">
                    <option value="replace">{{ t('insertModeReplace') }}</option>
                    <option value="append">{{ t('insertModeAppend') }}</option>
                    <option value="prepend">{{ t('insertModePrepend') }}</option>
                </select>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {{ t(currentWorkflowConfig.insertHelpKey || 'insertModeHelpTxt') }}
                </div>
            </div>
            <!-- Common Separator -->
            <div class="mb-3" v-if="currentWorkflowConfig.hasInsertMode"
                 v-show="['append', 'prepend'].includes(workflowParams[form.workflow_type].insert_mode)">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('separatorLabel') }}</label>
                <input type="text"
                       class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                       v-model="workflowParams[form.workflow_type].separator"
                       @input="saveWorkflowParam('separator')"
                       :placeholder="t(currentWorkflowConfig.separatorPlaceholderKey || 'separatorPlaceholderSimple')">
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1"
                     v-html="t(currentWorkflowConfig.separatorHelpKey || 'separatorHelp')"></div>
            </div>

            <!-- TXT Specific -->
            <div class="mb-3" v-if="form.workflow_type === 'txt'">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('segmentModeLabel') }}</label>
                <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                        v-model="workflowParams.txt.segment_mode"
                        @change="saveWorkflowParam('segment_mode')">
                    <option value="line">{{ t('segmentModeLine') }}</option>
                    <option value="paragraph">{{ t('segmentModeParagraph') }}</option>
                    <option value="none">{{ t('segmentModeNone') }}</option>
                </select>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('segmentModeHelp') }}</div>
            </div>
            <!-- XLSX Specific -->
            <div class="mb-3" v-if="form.workflow_type === 'xlsx'">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('xlsxTranslateRegionsLabel') }}</label>
                <textarea class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                          v-model="workflowParams.xlsx.translate_regions"
                          @input="saveWorkflowParam('translate_regions')" rows="3"
                          :placeholder="t('xlsxTranslateRegionsPlaceholder')"></textarea>
            </div>
            <!-- JSON Specific -->
            <div class="mb-3" v-if="form.workflow_type === 'json'">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('jsonPathLabel') }}</label>
                <textarea class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                          :class="{'border-red-500 dark:border-red-400': errors.json_paths}"
                          v-model="workflowParams.json.json_paths"
                          @input="saveWorkflowParam('json_paths'); clearError('json_paths')"
                          rows="4" required
                          :placeholder="t('jsonPathPlaceholder')"></textarea>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1" v-html="t('jsonPathHelp')"></div>
            </div>
            <!-- DXF Specific -->
            <div class="mb-3 space-y-2" v-if="['dxf', 'dwg'].includes(form.workflow_type)">
                <div v-if="form.workflow_type === 'dwg'" class="space-y-2 mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {{ label('dwgOdaPathLabel', dwgFallback.odaPathLabel) }}
                        <a href="https://www.opendesign.com/guestfiles/oda_file_converter" target="_blank" class="ml-1 text-primary hover:underline">
                            <Heroicon name="ArrowTopRightOnSquareIcon" class="w-4 h-4 inline" />
                        </a>
                    </label>
                    <div class="flex">
                        <input type="text"
                               class="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-l bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                               v-model="workflowParams.dwg.oda_path"
                               @input="saveWorkflowParam('oda_path')"
                               :placeholder="label('dwgOdaPathPlaceholder', dwgFallback.odaPathPlaceholder)">
                        <button type="button"
                                class="px-3 py-1.5 text-sm border border-l-0 border-gray-300 dark:border-gray-600 rounded-r bg-gray-50 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-500 transition-colors"
                                @click="openOdaFilePicker">
                            {{ label('dwgOdaBrowseLabel', dwgFallback.odaBrowseLabel) }}
                        </button>
                        <input ref="odaFileInput"
                               type="file"
                               class="hidden"
                               accept=".exe,application/x-msdownload"
                               @change="handleOdaFileChange">
                    </div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">
                        {{ label('dwgOdaPathHelp', dwgFallback.odaPathHelp) }}
                    </div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {{ label('dwgOdaTimeoutLabel', dwgFallback.odaTimeoutLabel) }}
                    </label>
                    <input type="number" min="1"
                           class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                           v-model.number="workflowParams.dwg.oda_timeout"
                           @input="saveWorkflowParam('oda_timeout')">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {{ label('dwgOutputVersionLabel', dwgFallback.outputVersionLabel) }}
                    </label>
                    <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                            v-model="workflowParams.dwg.dwg_output_version"
                            @change="saveDwgOutputVersion">
                        <option v-for="version in dwgVersionOptions" :key="version" :value="version">{{ version }}</option>
                    </select>
                    <div class="text-sm text-gray-500 dark:text-gray-400">
                        {{ label('dwgOutputVersionHelp', dwgFallback.outputVersionHelp) }}
                    </div>
                </div>
                <Toggle v-model="workflowParams[form.workflow_type].clean_text"
                        :label="label('dxfCleanTextLabel', dxfFallback.cleanTextLabel)"
                        @update:modelValue="saveWorkflowParam('clean_text')" />
                <div class="text-sm text-gray-500 dark:text-gray-400 pl-12">
                    {{ label('dxfCleanTextHelp', dxfFallback.cleanTextHelp) }}
                </div>
                <Toggle v-model="workflowParams[form.workflow_type].filter_text"
                        :label="label('dxfFilterTextLabel', dxfFallback.filterTextLabel)"
                        @update:modelValue="saveWorkflowParam('filter_text')" />
                <div class="text-sm text-gray-500 dark:text-gray-400 pl-12">
                    {{ label('dxfFilterTextHelp', dxfFallback.filterTextHelp) }}
                </div>
                <div v-show="workflowParams[form.workflow_type].filter_text" class="grid grid-cols-1 gap-2 pl-12">
                    <Toggle v-model="workflowParams[form.workflow_type].filter_non_translatable"
                            :label="label('dxfFilterNonTranslatableLabel', dxfFallback.filterNonTranslatableLabel)"
                            @update:modelValue="saveWorkflowParam('filter_non_translatable')" />
                    <Toggle v-model="workflowParams[form.workflow_type].filter_target_lang"
                            :label="label('dxfFilterTargetLangLabel', dxfFallback.filterTargetLangLabel)"
                            @update:modelValue="saveWorkflowParam('filter_target_lang')" />
                </div>
                <Toggle v-model="workflowParams[form.workflow_type].ai_filter_enable"
                        :label="label('dxfAiFilterLabel', dxfFallback.aiFilterLabel)"
                        @update:modelValue="saveWorkflowParam('ai_filter_enable')" />
                <div class="text-sm text-gray-500 dark:text-gray-400 pl-12">
                    {{ label('dxfAiFilterHelp', dxfFallback.aiFilterHelp) }}
                </div>
                <div v-show="workflowParams[form.workflow_type].ai_filter_enable" class="pl-12">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {{ label('dxfAiFilterPromptLabel', dxfFallback.aiFilterPromptLabel) }}
                    </label>
                    <textarea class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                              v-model="workflowParams[form.workflow_type].ai_filter_prompt"
                              @input="saveWorkflowParam('ai_filter_prompt')"
                              rows="4"
                              :placeholder="label('dxfAiFilterPromptPlaceholder', dxfFallback.aiFilterPromptPlaceholder)"></textarea>
                </div>
            </div>
        </template>
        <!-- Markdown Parsing Settings (only shown for markdown_based workflow) -->
        <div v-if="form.workflow_type === 'markdown_based'">
            <div class="mb-3">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('parsingEngineLabel') }}</label>
                <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                        v-model="form.convert_engine"
                        @change="saveSetting('translator_convert_engin', form.convert_engine)">
                    <option value="identity" v-if="showIdentityOption">
                        {{ t('engineOptionIdentity') || '已经是markdown' }}
                    </option>
                    <option v-for="eng in enginList" :key="eng" :value="eng">
                        {{ t('engineOption' + capitalize(eng)) || eng }}
                    </option>
                </select>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('parsingEngineHelp') }}</div>
            </div>

            <!-- Mineru Cloud Config -->
            <div v-if="form.convert_engine === 'mineru'">
                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Mineru Token
                        <a href="https://mineru.net/apiManage/token" target="_blank" class="ml-1 text-primary hover:underline">
                            <Heroicon name="ArrowTopRightOnSquareIcon" class="w-4 h-4 inline" />
                        </a>
                    </label>
                    <div class="flex">
                        <input :type="showMineruToken ? 'text' : 'password'"
                               autocomplete="new-password"
                               class="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-l bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                               :class="{'border-red-500 dark:border-red-400': errors.mineru_token}"
                               v-model="form.mineru_token"
                               @change="saveSetting('translator_mineru_token', form.mineru_token); clearError('mineru_token')"
                               :placeholder="t('mineruTokenPlaceholder')">
                        <button class="px-3 py-1.5 text-sm border border-l-0 border-gray-300 dark:border-gray-600 rounded-r bg-gray-50 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-500 transition-colors"
                                type="button"
                                @click="emit('update:showMineruToken', !showMineruToken)">
                            <Heroicon v-if="showMineruToken" name="EyeSlashIcon" class="w-5 h-5" />
                            <Heroicon v-else name="EyeIcon" class="w-5 h-5" />
                        </button>
                    </div>
                </div>
                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('modelVersionLabel') }}</label>
                    <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                            v-model="form.model_version"
                            @change="saveSetting('translator_model_version', form.model_version)">
                        <option value="vlm">{{ t('modelVersionVlm') }}</option>
                        <option value="pipeline">{{ t('modelVersionPipline') }}</option>
                    </select>
                    <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('modelVersionHelp') }}</div>
                </div>
                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruLanguageLabel') }}</label>
                    <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                            v-model="form.mineru_language"
                            @change="saveSetting('translator_mineru_language', form.mineru_language)">
                        <option v-for="lang in mineruLangOptions" :key="lang.val" :value="lang.val">
                            {{ lang.label }}
                        </option>
                    </select>
                </div>
            </div>

            <!-- Mineru Local Deploy Config -->
            <div v-if="form.convert_engine === 'mineru_deploy'"
                 class="border border-gray-300 dark:border-gray-600 p-3 rounded mb-3">
                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployBaseUrlLabel') }}</label>
                    <input type="url"
                           class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                           :class="{'border-red-500 dark:border-red-400': errors.mineru_deploy_base_url}"
                           v-model="form.mineru_deploy_base_url"
                           @change="saveSetting('mineru_deploy_base_url', form.mineru_deploy_base_url); clearError('mineru_deploy_base_url')"
                           required :placeholder="t('mineruDeployBaseUrlPlaceholder')">
                </div>
                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployBackendLabel') }}</label>
                    <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                            v-model="form.mineru_deploy_backend"
                            @change="saveSetting('mineru_deploy_backend', form.mineru_deploy_backend)">
                        <option value="pipeline">pipeline</option>
                        <option value="vlm-auto-engine">vlm-auto-engine</option>
                        <option value="vlm-http-client">vlm-http-client</option>
                        <option value="hybrid-auto-engine">hybrid-auto-engine</option>
                        <option value="hybrid-http-client">hybrid-http-client</option>
                    </select>
                </div>

                <div class="mb-3">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployParseMethodLabel') }}</label>
                    <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                            v-model="form.mineru_deploy_parse_method"
                            @change="saveSetting('mineru_deploy_parse_method', form.mineru_deploy_parse_method)">
                        <option value="auto">auto</option>
                        <option value="txt">txt</option>
                        <option value="ocr">ocr</option>
                    </select>
                </div>

                <!-- Condition: If Backend is Pipeline or Hybrid, show Lang List -->
                <div class="mb-3"
                     v-if="['pipeline', 'hybrid-auto-engine', 'hybrid-http-client'].includes(form.mineru_deploy_backend)">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployLangListLabel') }}</label>
                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        <label v-for="lang in mineruLangOptions" :key="lang.val"
                               class="inline-flex items-center gap-2 cursor-pointer">
                            <input type="checkbox"
                                   :value="lang.val"
                                   v-model="form.mineru_deploy_lang_list"
                                   @change="saveSettingArray('mineru_deploy_lang_list', form.mineru_deploy_lang_list)"
                                   class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary dark:border-gray-600 dark:bg-gray-700">
                            <span class="text-sm text-gray-700 dark:text-gray-300">{{ lang.label }}</span>
                        </label>
                    </div>
                </div>

                <!-- Condition: If Backend is vlm-http-client or hybrid-http-client, show Server URL -->
                <div class="mb-3"
                     v-if="['vlm-http-client', 'hybrid-http-client'].includes(form.mineru_deploy_backend)">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployServerUrlLabel') }}</label>
                    <input type="url"
                           class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                           v-model="form.mineru_deploy_server_url"
                           @change="saveSetting('mineru_deploy_server_url', form.mineru_deploy_server_url)"
                           :placeholder="t('mineruDeployServerUrlPlaceholder')">
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div class="mb-3">
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployStartPageLabel') }}</label>
                        <input type="number"
                               class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                               v-model="form.mineru_deploy_start_page"
                               @change="saveSetting('mineru_deploy_start_page', form.mineru_deploy_start_page)"
                               min="0">
                    </div>
                    <div class="mb-3">
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('mineruDeployEndPageLabel') }}</label>
                        <input type="number"
                               class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                               v-model="form.mineru_deploy_end_page"
                               @change="saveSetting('mineru_deploy_end_page', form.mineru_deploy_end_page)"
                               min="0">
                    </div>
                </div>
                <Toggle v-model="form.mineru_deploy_formula_enable"
                        :label="t('mineruDeployFormulaEnableLabel')"
                        @update:modelValue="saveSetting('mineru_deploy_formula_enable', form.mineru_deploy_formula_enable)"
                        class="mb-2" />
                <Toggle v-model="form.mineru_deploy_table_enable"
                        :label="t('mineruDeployTableEnableLabel')"
                        @update:modelValue="saveSetting('mineru_deploy_table_enable', form.mineru_deploy_table_enable)"
                        class="mb-2" />
            </div>


            <div class="mt-3">
                <Toggle v-if="ocrOptions.showFormula"
                        v-model="form.formula_ocr"
                        :label="t('formulaOcrLabel')"
                        @update:modelValue="saveSetting('translator_formula_ocr', form.formula_ocr)"
                        class="mb-2" />
                <Toggle v-if="ocrOptions.showCode"
                        v-model="form.code_ocr"
                        :label="t('codeOcrLabel')"
                        @update:modelValue="saveSetting('translator_code_ocr', form.code_ocr)"
                        class="mb-2" />
            </div>

            <!-- Markdown to Docx Engine Selector -->
            <div class="border-t border-gray-200 dark:border-gray-700 mt-3 pt-3">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('md2docxEngineLabel') || 'Markdown转Docx引擎' }}</label>
                <select class="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary"
                        v-model="form.md2docx_engine"
                        @change="saveSetting('translator_md2docx_engine', form.md2docx_engine)">
                    <option :value="null">{{ t('engineOptionNone') || '不生成docx' }}</option>
                    <option value="auto">{{ t('engineOptionAuto') || '自动选择' }}</option>
                    <option value="python">{{ t('engineOptionPython') || '纯Python' }}</option>
                    <option value="pandoc">{{ t('engineOptionPandoc') || 'Pandoc' }}</option>
                </select>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('md2docxEngineHelp') || '选择将Markdown导出为Docx的方式' }}</div>
            </div>
        </div>
    </Collapse>
</template>

<script setup>
import { computed, inject, ref } from 'vue';
import { mineruLangOptions } from '../../constants/mineruLanguages';
import { capitalize } from '../../utils/helpers';
import Collapse from '../ui/Collapse.vue';
import Button from '../ui/Button.vue';
import Toggle from '../ui/Toggle.vue';
import Heroicon from '../ui/Heroicon.vue';

const props = defineProps({
    t: Function,
    enginList: Array,
    showMineruToken: Boolean,
    showIdentityOption: Boolean,
});

const emit = defineEmits([
    'update:showMineruToken',
    'openDefaultWorkflowModal',
]);

// Inject from parent
const form = inject('form');
const workflowParams = inject('workflowParams');
const currentLang = inject('currentLang', ref('zh'));
const errors = inject('errors');
const saveSetting = inject('saveSetting');
const saveSettingArray = inject('saveSettingArray');
const saveWorkflowParam = inject('saveWorkflowParam');
const clearError = inject('clearError');

// Local state for collapse
const isWorkflowConfigOpen = ref(false);

const openDefaultWorkflowModal = () => {
    emit('openDefaultWorkflowModal');
};

const fallbackText = (fallback) => {
    if (typeof fallback === 'string') return fallback;
    const lang = currentLang?.value || localStorage.getItem('ui_language') || 'zh';
    return fallback?.[lang] || fallback?.en || '';
};

const label = (key, fallback) => {
    const value = props.t?.(key);
    return value && value !== key ? value : fallbackText(fallback);
};

const dxfFallback = {
    cleanTextLabel: {
        zh: '翻译前清洗文本',
        en: 'Clean text before translation',
        vi: 'Làm sạch văn bản trước khi dịch'
    },
    cleanTextHelp: {
        zh: '去除首尾空白，合并多余空格，规范全角字符，并保留必要换行后再进行筛选和翻译。',
        en: 'Trim leading and trailing spaces, merge repeated spaces, normalize full-width characters, and keep useful line breaks before filtering and translation.',
        vi: 'Cắt khoảng trắng ở đầu/cuối, gộp khoảng trắng lặp lại, chuẩn hóa ký tự full-width và giữ các dòng xuống cần thiết trước khi lọc và dịch.'
    },
    filterTextLabel: {
        zh: '启用文本筛选',
        en: 'Enable text filtering',
        vi: 'Bật lọc văn bản'
    },
    filterTextHelp: {
        zh: '开启后可通过下方细分项减少不必要的翻译内容。',
        en: 'When enabled, use the detailed filters below to reduce unnecessary translation.',
        vi: 'Khi bật, dùng các bộ lọc chi tiết bên dưới để giảm nội dung không cần dịch.'
    },
    filterNonTranslatableLabel: {
        zh: '过滤非译字符串：纯数字、符号、工程位号等',
        en: 'Filter non-translatable strings: numbers, symbols, engineering tags, etc.',
        vi: 'Lọc chuỗi không cần dịch: số, ký hiệu, mã kỹ thuật, v.v.'
    },
    filterTargetLangLabel: {
        zh: '过滤已经是目标语言的内容',
        en: 'Filter text already in the target language',
        vi: 'Lọc văn bản đã là ngôn ngữ đích'
    }
    ,
    aiFilterLabel: {
        zh: 'AI text filtering',
        en: 'AI text filtering',
        vi: 'AI text filtering'
    },
    aiFilterHelp: {
        zh: '使用当前 AI 模型在翻译前判断去重后的 DXF/DWG 文本是否需要翻译。默认提示词偏保守，表头优先翻译。',
        en: 'Use the configured AI model to decide whether deduplicated DXF/DWG text should be translated. The default prompt is conservative and prioritizes table headers.',
        vi: 'Dung mo hinh AI hien tai de quyet dinh van ban DXF/DWG da khu trung co can dich hay khong. Prompt mac dinh than trong va uu tien dau bang.'
    },
    aiFilterPromptLabel: {
        zh: 'AI 筛选 Prompt',
        en: 'AI filter prompt',
        vi: 'AI filter prompt'
    },
    aiFilterPromptPlaceholder: {
        zh: '默认提示词已自动填入，可按需修改。',
        en: 'The default prompt is filled in automatically and can be edited.',
        vi: 'Prompt mac dinh da duoc dien tu dong va co the chinh sua.'
    }
};

const dwgFallback = {
    odaPathLabel: {
        zh: 'ODA File Converter 路径',
        en: 'ODA File Converter path',
        vi: 'Duong dan ODA File Converter'
    },
    odaPathPlaceholder: {
        zh: '留空自动识别，或填写 ODAFileConverter.exe 路径',
        en: 'Leave blank to auto-detect, or enter the ODAFileConverter.exe path',
        vi: 'De trong de tu dong tim, hoac nhap duong dan ODAFileConverter.exe'
    },
    odaPathHelp: {
        zh: '启动时会自动识别已安装路径。无法识别时，可选择 ODAFileConverter.exe 或手动填写完整路径。',
        en: 'The app auto-detects the installed path at startup. If it is not detected, select ODAFileConverter.exe or enter the full path manually.',
        vi: 'Ung dung tu nhan dien duong dan khi khoi dong. Neu khong tim thay, hay chon ODAFileConverter.exe hoac nhap duong dan day du.'
    },
    odaBrowseLabel: {
        zh: '选择文件',
        en: 'Select file',
        vi: 'Chon tep'
    },
    odaTimeoutLabel: {
        zh: '转换超时（秒）',
        en: 'Conversion timeout (seconds)',
        vi: 'Thoi gian cho chuyen doi (giay)'
    },
    outputVersionLabel: {
        zh: 'DWG 输出版本',
        en: 'DWG output version',
        vi: 'Phien ban DWG dau ra'
    },
    outputVersionHelp: {
        zh: '默认 ACAD2007。每次任务生成所选版本的 DWG 下载文件。',
        en: 'Defaults to ACAD2007. Each task produces one DWG download in the selected version.',
        vi: 'Mac dinh ACAD2007. Moi tac vu tao mot tep DWG theo phien ban da chon.'
    }
};

const dwgVersionOptions = ['ACAD2007', 'ACAD2010', 'ACAD2013', 'ACAD2018', 'ACAD2021'];
const odaFileInput = ref(null);

const openOdaFilePicker = () => {
    odaFileInput.value?.click();
};

const looksLikeRealPath = (value) => /[A-Za-z]:\\|\\\\|^\//.test(value || '');

const handleOdaFileChange = (event) => {
    const file = event.target.files?.[0];
    const candidate = file?.path || event.target.value || '';
    if (candidate && looksLikeRealPath(candidate) && !/^C:\\fakepath\\/i.test(candidate)) {
        workflowParams.dwg.oda_path = candidate;
        saveWorkflowParam('oda_path');
    }
    event.target.value = '';
};

const saveDwgOutputVersion = () => {
    const version = workflowParams.dwg.dwg_output_version || 'ACAD2007';
    workflowParams.dwg.dwg_output_version = version;
    workflowParams.dwg.dwg_output_versions = [version];
    saveWorkflowParam('dwg_output_version');
};

const currentWorkflowConfig = computed(() => {
    const map = {
        'txt': {
            titleKey: 'txtSettingsTitleText',
            icon: 'bi-filetype-txt',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpTxt'
        },
        'docx': {
            titleKey: 'docxSettingsTitleText',
            icon: 'bi-file-earmark-word',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpDocx'
        },
        'xlsx': {
            titleKey: 'xlsxSettingsTitleText',
            icon: 'bi-file-earmark-spreadsheet',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpXlsx'
        },
        'srt': {
            titleKey: 'srtSettingsTitleText',
            icon: 'bi-file-text',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpSrt'
        },
        'epub': {
            titleKey: 'epubSettingsTitleText',
            icon: 'bi-book',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpEpub'
        },
        'html': {
            titleKey: 'htmlSettingsTitleText',
            icon: 'bi-filetype-html',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpHtml'
        },
        'ass': {
            titleKey: 'assSettingsTitleText',
            icon: 'bi-file-easel',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpAss',
            separatorHelpKey: 'separatorHelpAss',
            separatorPlaceholderKey: 'separatorPlaceholderAss'
        },
        'pptx': {
            titleKey: 'pptxSettingsTitleText',
            icon: 'bi-file-slides',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpPptx'
        },
        'dxf': {
            titleKey: 'dxfSettingsTitleText',
            icon: 'bi-file-earmark',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpDxf'
        },
        'dwg': {
            titleKey: 'dwgSettingsTitleText',
            icon: 'bi-file-earmark',
            hasInsertMode: true,
            insertHelpKey: 'insertModeHelpDxf'
        },
        'json': {titleKey: 'jsonSettingsTitleText', icon: 'bi-signpost-split', hasInsertMode: false},
    };
    return map[form.workflow_type];
});

const ocrOptions = computed(() => ({
    showFormula: ['mineru', 'docling'].includes(form.convert_engine),
    showCode: form.convert_engine === 'docling'
}));
</script>
