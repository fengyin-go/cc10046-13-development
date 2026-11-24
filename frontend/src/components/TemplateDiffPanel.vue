<template>
  <section id="template-diff-panel" class="lab-panel" data-testid="template-diff-panel">
    <header class="lab-head">
      <div>
        <h3>模板字段差异视图 · 采样对照</h3>
        <p>
          选择同一份原始网页样本和新旧模板，按完全相同的原文版本解析，逐项比较字段覆盖与具体内容。
          来源更正后生成的是新版本证据；早先对照和旧证据不会被覆盖。
        </p>
      </div>
      <span class="lab-badge" data-testid="same-raw-badge">两份模板对齐同一份网页原文</span>
    </header>

    <div v-if="errorMessage" class="lab-error" role="alert" data-testid="template-diff-error">
      {{ errorMessage }}
    </div>
    <div v-if="noticeMessage" class="lab-notice" role="status" data-testid="template-diff-notice">
      {{ noticeMessage }}
    </div>

    <div class="control-grid">
      <label>
        <span>原始网页样本</span>
        <select v-model="sampleId" data-testid="sample-select">
          <option v-for="item in samples" :key="item.sample_id" :value="item.sample_id">
            {{ item.sample_id }}｜{{ item.name }}
          </option>
        </select>
      </label>
      <label>
        <span>旧模板</span>
        <select v-model="oldTemplateId" data-testid="old-template-select">
          <option v-for="item in templates" :key="item.template_id" :value="item.template_id">
            {{ item.name }}
          </option>
        </select>
      </label>
      <label>
        <span>新模板</span>
        <select v-model="newTemplateId" data-testid="new-template-select">
          <option v-for="item in templates" :key="item.template_id" :value="item.template_id">
            {{ item.name }}
          </option>
        </select>
      </label>
      <label>
        <span>对齐的原文版本</span>
        <select v-model="versionId" data-testid="sample-version-select">
          <option value="">当前已核对版本</option>
          <option v-for="version in versions" :key="version.version_id" :value="version.version_id">
            {{ version.version_label }}
          </option>
        </select>
      </label>
      <button class="btn primary" type="button" data-testid="compare-templates" :disabled="loading" @click="compare">
        {{ loading ? '对照生成中…' : '生成字段差异对照' }}
      </button>
    </div>

    <div class="source-card" data-testid="source-card">
      <div>
        <strong>来源原文状态：</strong>
        <span data-testid="source-status">{{ activeSample?.source_status || '读取中' }}</span>
        <div class="source-values" data-testid="current-source-values">
          当前来源值：规格 {{ activeSample?.current_values?.['规格'] ?? '—' }}；
          颜色 {{ activeSample?.current_values?.['颜色'] ?? '—' }}
        </div>
      </div>
      <div class="source-actions">
        <input
          v-model="correctionColor"
          class="color-input"
          data-testid="source-color-input"
          aria-label="更正后的颜色"
          placeholder="输入更正后的颜色，如绿色"
        />
        <button class="btn" type="button" data-testid="correct-source" @click="correctSource()">
          更正来源颜色
        </button>
        <button class="btn ghost" type="button" data-testid="correct-source-green" @click="correctGreen">
          模拟页面已变绿
        </button>
        <button class="btn primary" type="button" data-testid="refresh-confirm-source" @click="refreshAndConfirm">
          刷新并确认新原文
        </button>
        <button class="btn primary" type="button" data-testid="refresh-confirm-source" @click="refreshAndConfirm">
          刷新并确认新原文
        </button>
      </div>
    </div>

    <div class="raw-editor-card" data-testid="source-raw-editor-card">
      <label for="source-raw-editor">原始网页原文（可直接把页面中的蓝色更正为绿色后保存）</label>
      <textarea
        id="source-raw-editor"
        v-model="rawDraft"
        class="raw-editor"
        data-testid="source-raw-editor"
        rows="5"
        aria-label="原始网页原文编辑器"
      ></textarea>
      <div class="raw-editor-actions">
        <button class="btn" type="button" data-testid="save-raw-correction" @click="saveRawCorrection">
          保存原文更正
        </button>
        <span class="hint">保存只更新来源当前原文并记录更正，不会改写已经生成的对照证据。</span>
      </div>
    </div>

    <template v-if="currentDiff">
      <div class="alignment" data-testid="alignment-message">
        <strong>对齐校验：</strong>{{ currentDiff.alignment?.message }}
        <span class="mono">样本 {{ currentDiff.sample_id }} / 版本 {{ currentDiff.sample_version_id }} / 摘要 {{ currentDiff.raw_hash }}</span>
      </div>

      <div class="diff-summary" data-testid="diff-summary">
        <span>差异项：<strong>{{ currentDiff.difference_count }}</strong></span>
        <span>旧模板字段：{{ (currentDiff.old_template?.fields || []).join('、') }}</span>
        <span>新模板字段：{{ (currentDiff.new_template?.fields || []).join('、') }}</span>
      </div>

      <div class="table-scroll">
        <table class="data-table diff-table" data-testid="template-field-diff-table">
          <thead>
            <tr>
              <th>字段</th>
              <th>旧模板解析内容</th>
              <th>新模板解析内容</th>
              <th>差异类型</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in currentDiff.fields"
              :key="row.field"
              :data-testid="`diff-row-${row.field}`"
              :data-status="row.status"
              :class="{ different: row.different }"
            >
              <td data-label="字段"><strong>{{ row.field }}</strong></td>
              <td data-label="旧模板" class="value-cell" data-testid="diff-old-value">{{ row.old_value || '未覆盖/空' }}</td>
              <td data-label="新模板" class="value-cell" data-testid="diff-new-value">{{ row.new_value || '未覆盖/空' }}</td>
              <td data-label="差异" data-testid="diff-change-type">
                <span :class="['diff-tag', row.status]">{{ row.change_type }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="confirm-bar">
        <button class="btn primary" type="button" data-testid="confirm-sample-for-mapping" @click="confirmForMapping">
          确认该网页样本并送入字段映射
        </button>
        <span v-if="selection?.comparison_id === currentDiff.diff_id" class="confirmed" data-testid="sample-selected">
          已确认：字段映射将读取 {{ currentDiff.sample_version_label }}
        </span>
      </div>

      <details class="raw-details" open>
        <summary>本次对照对齐的网页原文证据（不可变）</summary>
        <pre data-testid="raw-evidence">{{ currentDiff.raw }}</pre>
      </details>
    </template>

    <section class="history" data-testid="comparison-history">
      <h4>采样对照记录与旧证据</h4>
      <p class="hint">来源更正后，这里的历史对照仍保留当时解析到的具体内容；再次进入采样对照，旧证据里仍是此前取得的蓝色。点击记录可重新查看。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>对照编号</th>
            <th>输入版本</th>
            <th>旧模板值</th>
            <th>新模板值</th>
            <th>差异数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in comparisons" :key="item.diff_id" :data-testid="`history-row-${item.diff_id}`">
            <td>{{ item.diff_id }}</td>
            <td>{{ item.sample_version_id }}<br /><small>{{ item.input_version_label }}</small></td>
            <td data-testid="history-old-values">{{ formatValues(item.old_values) }}</td>
            <td data-testid="history-new-values">{{ formatValues(item.new_values) }}</td>
            <td>{{ item.difference_count }}</td>
            <td>
              <button class="link" type="button" :data-testid="`view-history-${item.diff_id}`" @click="openDiff(item.diff_id)">
                查看旧对照
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { sampleLabApi, type LabRecord } from '@/api/sample-lab'

const samples = ref<LabRecord[]>([])
const templates = ref<LabRecord[]>([])
const comparisons = ref<LabRecord[]>([])
const selection = ref<LabRecord | null>(null)
const currentDiff = ref<LabRecord | null>(null)
const sampleId = ref('WEB-PRODUCT-001')
const oldTemplateId = ref('TPL-OLD-SPEC')
const newTemplateId = ref('TPL-NEW-COLOR')
const versionId = ref('SV-001')
const correctionColor = ref('绿色')
const rawDraft = ref('')
const loading = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')

const activeSample = computed(() => samples.value.find((item) => item.sample_id === sampleId.value) || null)
const versions = computed<LabRecord[]>(() => activeSample.value?.versions || [])

function formatValues(values: Record<string, unknown> | undefined): string {
  if (!values) return '—'
  const text = Object.entries(values)
    .filter(([, value]) => value !== '' && value !== null && value !== undefined)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join('，')
  return text || '—'
}

async function loadState(selectDiffId?: string) {
  errorMessage.value = ''
  try {
    const state = await sampleLabApi.state()
    samples.value = state.samples as LabRecord[]
    templates.value = state.templates as LabRecord[]
    comparisons.value = state.comparisons as LabRecord[]
    selection.value = (state.selection as LabRecord | null) ?? null
    sampleId.value = (state.defaults as LabRecord).sample_id
    oldTemplateId.value = (state.defaults as LabRecord).old_template_id
    newTemplateId.value = (state.defaults as LabRecord).new_template_id
    rawDraft.value = activeSample.value?.current_raw ? String(activeSample.value.current_raw) : ''
    const baseline = comparisons.value.find((item) => item.sample_version_id === 'SV-001')
    const targetId = selectDiffId
      || currentDiff.value?.diff_id
      || baseline?.diff_id
      || comparisons.value[comparisons.value.length - 1]?.diff_id
    if (targetId) await openDiff(String(targetId))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板对照数据读取失败'
  }
}

async function openDiff(diffId: string) {
  try {
    currentDiff.value = await sampleLabApi.diff(diffId)
    sampleId.value = currentDiff.value.sample_id
    versionId.value = currentDiff.value.sample_version_id
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '旧对照读取失败'
  }
}

async function compare() {
  loading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    currentDiff.value = await sampleLabApi.compare({
      sample_id: sampleId.value,
      old_template_id: oldTemplateId.value,
      new_template_id: newTemplateId.value,
      sample_version_id: versionId.value || undefined,
    })
    noticeMessage.value = `已按 ${currentDiff.value.input_version_label} 对齐同一份原文完成对照。`
    await loadState(String(currentDiff.value.diff_id))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成字段差异失败'
  } finally {
    loading.value = false
  }
}

async function confirmForMapping() {
  if (!currentDiff.value) return
  errorMessage.value = ''
  try {
    const result = await sampleLabApi.selectDiff(String(currentDiff.value.diff_id))
    const selected = (result.context as LabRecord).selection as LabRecord
    selection.value = selected
    try {
      window.localStorage.setItem('sampleLabSelection', JSON.stringify(selected))
    } catch {
      // 浏览器存储不可用时，后端内存选择仍可完成本次流程。
    }
    noticeMessage.value = '已确认选中的网页样本版本；请进入字段映射页面发起试跑和校对。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '样本确认失败'
  }
}

async function correctSource(color?: string) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const nextColor = color ?? correctionColor.value.trim()
  if (!nextColor) {
    errorMessage.value = '请先输入更正后的颜色'
    return
  }
  try {
    const result = await sampleLabApi.correctSource(sampleId.value, { color: nextColor })
    const sample = result.sample as LabRecord
    const index = samples.value.findIndex((item) => item.sample_id === sample.sample_id)
    if (index >= 0) samples.value[index] = sample
    noticeMessage.value = `来源已更正为${nextColor}。当前对照仍是固定旧证据；可刷新并确认新原文后生成新对照。`
    await loadState(currentDiff.value ? String(currentDiff.value.diff_id) : undefined)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '来源更正失败'
  }
}

function correctGreen() {
  correctionColor.value = '绿色'
  return correctSource('绿色')
}

async function saveRawCorrection() {
  errorMessage.value = ''
  noticeMessage.value = ''
  if (!rawDraft.value.trim()) {
    errorMessage.value = '网页原文不能为空'
    return
  }
  try {
    await sampleLabApi.correctSource(sampleId.value, { raw: rawDraft.value })
    noticeMessage.value = '原文更正已保存；历史对照仍保留更正前取得的证据。'
    await loadState(currentDiff.value ? String(currentDiff.value.diff_id) : undefined)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '原文更正保存失败'
  }
}

async function refreshAndConfirm() {
  errorMessage.value = ''
  try {
    const result = await sampleLabApi.refreshConfirm(sampleId.value)
    const sample = result.sample as LabRecord
    const index = samples.value.findIndex((item) => item.sample_id === sample.sample_id)
    if (index >= 0) samples.value[index] = sample
    versionId.value = sample.confirmed_version_id
    noticeMessage.value = '已刷新并确认新原文，正在按新版本生成对照；蓝色旧证据仍可在历史记录中查看。'
    await compare()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新确认失败'
  }
}

onMounted(() => {
  void loadState()
})
</script>

<style scoped>
.lab-panel { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin: 12px 0 16px; }
.lab-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.lab-head h3 { margin: 0 0 6px; font-size: 17px; }
.lab-head p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.7; }
.lab-badge { flex: none; background: #ecfdf3; color: #027a48; border: 1px solid #abefc6; border-radius: 999px; padding: 5px 10px; font-size: 12px; }
.control-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; align-items: end; margin: 14px 0; }
.control-grid label, .source-actions label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--muted); }
.control-grid select, .control-grid input, .color-input { border: 1px solid var(--border); border-radius: 6px; padding: 7px 9px; font-size: 13px; background: #fff; color: #1f2937; }
.source-card { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; font-size: 13px; }
.source-values { color: var(--muted); margin-top: 5px; }
.source-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.color-input { width: 150px; }
.raw-editor-card { border: 1px dashed #94a3b8; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #fcfcfd; }
.raw-editor-card label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.raw-editor { width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; resize: vertical; }
.raw-editor-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.alignment { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; border-radius: 8px; padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; word-break: break-all; }
.diff-summary { display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 2px; font-size: 13px; color: #334155; }
.table-scroll { overflow-x: auto; }
.diff-table tr.different { background: #fffbeb; }
.value-cell { min-width: 150px; }
.diff-tag { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; border: 1px solid transparent; }
.diff-tag.added { color: #027a48; background: #ecfdf3; border-color: #abefc6; }
.diff-tag.removed { color: #b42318; background: #fef3f2; border-color: #fecdca; }
.diff-tag.changed { color: #b54708; background: #fffaeb; border-color: #fedf89; }
.diff-tag.unchanged { color: #475467; background: #f2f4f7; border-color: #e4e7ec; }
.confirm-bar { display: flex; align-items: center; gap: 12px; margin: 12px 0; flex-wrap: wrap; }
.confirmed { color: #027a48; font-size: 13px; font-weight: 600; }
.raw-details { margin-top: 8px; }
.raw-details summary { cursor: pointer; font-size: 13px; font-weight: 600; }
.raw-details pre { background: #0f172a; color: #dbeafe; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12px; line-height: 1.6; }
.history { margin-top: 18px; }
.history h4 { margin: 0 0 4px; }
.hint { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.lab-error { background: #fef3f2; border: 1px solid #fecdca; color: #b42318; padding: 9px 12px; border-radius: 8px; font-size: 13px; margin: 10px 0; }
.lab-notice { background: #ecfdf3; border: 1px solid #abefc6; color: #027a48; padding: 9px 12px; border-radius: 8px; font-size: 13px; margin: 10px 0; }
@media (max-width: 760px) { .lab-head { flex-direction: column; } }
</style>
