<template>
  <section id="field-proofread-panel" class="proof-panel" data-testid="field-proofread-panel">
    <header class="proof-head">
      <div>
        <h3>字段映射校对入口</h3>
        <p>
          先在「抽取模板 → 模板字段差异视图」确认网页样本，再在这里读取该次选中的具体原文版本。
          试跑和服务端回执都会记录输入版本、原文值、输入摘要与实际映射值，保证提交记录可追溯。
        </p>
      </div>
      <span class="entry-badge" data-testid="proofread-mapping-entry">
        当前映射方案：{{ mappingName || `#${mappingEntryId}` }}
      </span>
    </header>

    <div v-if="errorMessage" class="proof-error" role="alert" data-testid="proofread-error">{{ errorMessage }}</div>
    <div v-if="noticeMessage" class="proof-notice" role="status">{{ noticeMessage }}</div>

    <div class="context-grid">
      <div class="context-card" data-testid="selected-sample-context">
        <div class="card-title">
          <strong>模板差异视图选中的网页样本</strong>
          <button class="link" type="button" data-testid="reload-selected-sample" @click="loadContext">读取模板字段差异视图选中的网页样本</button>
        </div>
        <template v-if="selectionConfirmed && selection">
          <p class="ok-line" data-testid="context-confirmed">已读取用户确认的样本选择。</p>
          <dl class="kv">
            <dt>对照记录</dt><dd data-testid="context-comparison-id">{{ selection.comparison_id }}</dd>
            <dt>网页样本</dt><dd>{{ selection.sample_id }}</dd>
            <dt>输入版本</dt><dd data-testid="selected-sample-version">{{ selection.sample_version_id }}</dd>
            <dt>输入摘要</dt><dd class="mono">{{ selection.raw_hash }}</dd>
          </dl>
        </template>
        <template v-else>
          <p class="warn-line" data-testid="context-empty">
            尚未读到“确认并送入字段映射”的选择；可先使用当前已核对样本，或返回抽取模板页确认差异样本。
          </p>
        </template>
        <p class="source-status" data-testid="proofread-source-status">{{ context?.source_status }}</p>
      </div>

      <div class="context-card">
        <strong>本次校对使用哪一版输入？</strong>
        <label class="mode-option" :class="{ active: inputMode === 'checked_snapshot' }">
          <input v-model="inputMode" type="radio" value="checked_snapshot" data-testid="input-mode-snapshot" @change="trial = null" />
          <span>
            <b>使用已核对的旧样本</b>
            <small>固定读取蓝色证据 SV-001；即使线上来源已更正为绿色，回执仍对应蓝色旧输入。</small>
          </span>
        </label>
        <label class="mode-option" :class="{ active: inputMode === 'refresh_confirm' }">
          <input v-model="inputMode" type="radio" value="refresh_confirm" data-testid="input-mode-refresh" @change="trial = null" />
          <span>
            <b>刷新并确认新原文</b>
            <small>读取来源当前内容，生成并确认新版本；若颜色已变绿，试跑和回执应显示绿色。旧蓝色证据仍保留。</small>
          </span>
        </label>
        <div class="actions">
          <button class="btn" type="button" data-testid="run-trial" :disabled="loading" @click="runTrial">
            {{ loading ? '试跑中…' : '试跑映射' }}
          </button>
          <button class="btn primary" type="button" data-testid="submit-proofread" :disabled="submitting" @click="submitProofread">
            {{ submitting ? '提交核验中…' : '提交校对' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="trial" class="result-card trial-card" data-testid="trial-result">
      <h4>试跑结果：具体输入版本与实际映射值</h4>
      <div class="result-grid">
        <div>
          <span class="result-label">输入版本</span>
          <strong data-testid="trial-input-version">{{ trial.input_version_label }}</strong>
          <small class="mono" data-testid="trial-input-hash">摘要 {{ trial.input_hash }}</small>
        </div>
        <div>
          <span class="result-label">原文实际值</span>
          <div data-testid="trial-source-values">
            <span v-for="(value, key) in trial.source_values" :key="String(key)" class="value-pill source">
              {{ key }}={{ value }}
            </span>
          </div>
        </div>
        <div>
          <span class="result-label">实际映射值</span>
          <div data-testid="trial-mapped-values">
            <span
              v-for="detail in trial.mapping_details"
              :key="`${detail.source_field}-${detail.target_field}`"
              class="value-pill mapped"
              :data-testid="`mapping-detail-${detail.target_field}`"
            >
              {{ detail.source_field }} → {{ detail.target_field }}={{ formatMapped(detail.mapped_value) }}
            </span>
            <template v-if="!trial.mapping_details?.length">
              <span v-for="(value, key) in trial.mapped_values" :key="String(key)" class="value-pill mapped">
                {{ key }}={{ formatMapped(value) }}
              </span>
            </template>
          </div>
        </div>
      </div>
    </div>

    <div v-if="receipt" class="result-card receipt-card" data-testid="proofread-receipt">
      <h4>服务端回执与输入核验</h4>
      <p class="verified-line" data-testid="receipt-verified">
        ✅ {{ receipt.verification }}（verified={{ String(receipt.verified) }}）
      </p>
      <div class="receipt-grid">
        <div><span>回执编号</span><strong data-testid="receipt-id">{{ receipt.receipt_id }}</strong></div>
        <div><span>校对记录</span><strong>{{ receipt.record_id }}</strong></div>
        <div><span>本次输入版本</span><strong data-testid="receipt-input-version">{{ receipt.input_version_label }}</strong></div>
        <div><span>输入摘要核验</span><strong class="mono" data-testid="receipt-input-hash">{{ receipt.input_hash }}｜verified={{ String(receipt.input_hash_verified) }}</strong></div>
        <div class="wide"><span>服务端核验的原文输入</span><strong data-testid="receipt-source-values">{{ formatObject(receipt.source_values) }}</strong></div>
        <div class="wide"><span>服务端计算的实际映射值</span><strong data-testid="receipt-mapped-values">{{ formatObject(receipt.mapped_values) }}</strong></div>
        <div class="wide"><span>旧模板解析值</span><strong>{{ formatObject(receipt.old_template_values) }}</strong></div>
        <div class="wide"><span>新模板解析值</span><strong>{{ formatObject(receipt.new_template_values) }}</strong></div>
      </div>
    </div>

    <section class="records" data-testid="proofread-records">
      <h4>日常字段校对提交记录（按实际样本版本）</h4>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>记录/回执</th>
              <th>实际输入版本</th>
              <th>原文值</th>
              <th>实际映射值</th>
              <th>摘要/核验</th>
              <th>提交时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.record_id" :data-testid="`proofread-row-${record.record_id}`">
              <td>{{ record.record_id }}<br /><small>{{ record.receipt_id }}</small></td>
              <td data-testid="record-input-version">{{ record.input_version_label }}</td>
              <td data-testid="record-source-values">{{ formatObject(record.source_values) }}</td>
              <td data-testid="record-mapped-values">{{ formatObject(record.mapped_values) }}</td>
              <td class="mono">{{ record.input_hash }}<br />verified={{ String(record.verified) }}</td>
              <td>{{ record.submitted_at }}</td>
            </tr>
            <tr v-if="!records.length">
              <td colspan="6" class="empty-state">暂无字段校对提交记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { sampleLabApi, type LabRecord } from '@/api/sample-lab'

const props = defineProps<{
  mappingEntryId?: number | string
  mappingName?: string
  mappingRow?: Record<string, unknown> | null
}>()

const context = ref<LabRecord | null>(null)
const localSelection = ref<LabRecord | null>(null)
const inputMode = ref<'checked_snapshot' | 'refresh_confirm'>('checked_snapshot')
const trial = ref<LabRecord | null>(null)
const receipt = ref<LabRecord | null>(null)
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')

const selection = computed<LabRecord | null>(
  () => (context.value?.selection as LabRecord | undefined) ?? localSelection.value,
)
const selectionConfirmed = computed(() =>
  Boolean(context.value?.selection_confirmed || localSelection.value?.confirmed),
)
const records = computed<LabRecord[]>(() => (context.value?.proofreads as LabRecord[] | undefined) ?? [])
const rowRules = computed<LabRecord[] | undefined>(() => {
  const row = props.mappingRow
  if (!row) return undefined
  const splitFields = (value: unknown) =>
    String(value ?? '')
      .split(/[、,，;；\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  const sources = splitFields(row['来源字段'])
  const targets = splitFields(row['目标字段'])
  if (sources.length !== targets.length || !sources.includes('规格')) return undefined
  return sources.map((source, index) => ({
    source_field: source,
    source,
    target_field: targets[index],
    target: targets[index],
    transform: '',
    default: '',
  }))
})

function formatMapped(value: unknown): string {
  if (value === null || value === undefined || value === '') return '空'
  return String(value)
}

function formatObject(value: unknown): string {
  if (!value || typeof value !== 'object') return '—'
  return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${key}=${formatMapped(item)}`)
    .join('；')
}

function basePayload() {
  const selected = selection.value
  return {
    mapping_entry_id: props.mappingEntryId ?? 1,
    mapping_id: props.mappingName ? String(props.mappingName) : `FM-ENTRY-${props.mappingEntryId ?? 1}`,
    comparison_id: selected?.comparison_id,
    sample_id: context.value?.sample?.sample_id ?? 'WEB-PRODUCT-001',
    sample_version_id: inputMode.value === 'checked_snapshot' ? selected?.sample_version_id : undefined,
    input_hash: inputMode.value === 'checked_snapshot' ? selected?.raw_hash : undefined,
    input_mode: inputMode.value,
    mapping_rules: rowRules.value,
  }
}

async function loadContext() {
  errorMessage.value = ''
  try {
    context.value = await sampleLabApi.fieldContext()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段映射上下文读取失败'
  }
}

async function runTrial() {
  loading.value = true
  errorMessage.value = ''
  try {
    trial.value = await sampleLabApi.trial(basePayload())
    noticeMessage.value = `试跑完成：本次实际使用 ${trial.value.input_version_label}`
    return trial.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '映射试跑失败'
    return null
  } finally {
    loading.value = false
  }
}

async function submitProofread() {
  submitting.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const trialResult = trial.value ?? (await runTrial())
    if (!trialResult) throw new Error('试跑未成功，不能提交校对')
    const result = await sampleLabApi.submitProofread({
      ...basePayload(),
      trial_id: trialResult.trial_id,
      sample_id: trialResult.sample_id,
      sample_version_id: trialResult.sample_version_id,
      input_hash: trialResult.input_hash,
      mapped_values: trialResult.mapped_values,
    })
    receipt.value = (result.receipt as LabRecord) ?? result
    noticeMessage.value = String(result.message || '字段校对已提交')
    await loadContext()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段校对提交失败'
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.mappingEntryId,
  () => {
    receipt.value = null
    trial.value = null
  },
)

onMounted(() => {
  try {
    const stored = window.localStorage.getItem('sampleLabSelection')
    if (stored) localSelection.value = JSON.parse(stored) as LabRecord
  } catch {
    // 本地存储不可用时继续使用后端上下文中的选择。
  }
  void loadContext()
})
</script>

<style scoped>
.proof-panel { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin: 12px 0 16px; }
.proof-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.proof-head h3 { margin: 0 0 6px; font-size: 17px; }
.proof-head p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.7; }
.entry-badge { flex: none; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 999px; padding: 5px 10px; font-size: 12px; }
.context-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 14px 0; }
.context-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: #f8fafc; font-size: 13px; }
.card-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.kv { display: grid; grid-template-columns: 80px 1fr; gap: 5px 8px; margin: 8px 0 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; word-break: break-all; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; word-break: break-all; }
.ok-line { color: #027a48; font-weight: 600; margin: 4px 0; }
.warn-line { color: #b54708; background: #fffaeb; border: 1px solid #fedf89; border-radius: 6px; padding: 8px; }
.source-status { color: var(--muted); margin-bottom: 0; }
.mode-option { display: flex; gap: 9px; align-items: flex-start; padding: 9px; border: 1px solid var(--border); border-radius: 8px; margin-top: 9px; cursor: pointer; background: #fff; }
.mode-option.active { border-color: var(--brand); background: #eff6ff; }
.mode-option input { margin-top: 3px; }
.mode-option b { display: block; font-size: 13px; }
.mode-option small { display: block; color: var(--muted); line-height: 1.5; margin-top: 3px; }
.actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.result-card { border-radius: 8px; padding: 12px; margin: 12px 0; border: 1px solid; }
.trial-card { background: #f8fafc; border-color: var(--border); }
.receipt-card { background: #f0fdf4; border-color: #abefc6; }
.result-card h4 { margin: 0 0 10px; }
.result-grid { display: grid; grid-template-columns: 0.8fr 1.2fr 1.2fr; gap: 12px; }
.result-label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 5px; }
.value-pill { display: inline-block; border-radius: 999px; padding: 3px 9px; margin: 2px 4px 2px 0; font-size: 12px; }
.value-pill.source { background: #fffaeb; color: #b54708; border: 1px solid #fedf89; }
.value-pill.mapped { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
.verified-line { color: #027a48; font-weight: 600; font-size: 13px; }
.receipt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.receipt-grid div { display: flex; flex-direction: column; gap: 3px; }
.receipt-grid .wide { grid-column: 1 / -1; }
.receipt-grid span { color: var(--muted); font-size: 12px; }
.receipt-grid strong { font-size: 13px; word-break: break-word; }
.records { margin-top: 16px; }
.records h4 { margin: 0 0 10px; }
.table-scroll { overflow-x: auto; }
.proof-error { background: #fef3f2; border: 1px solid #fecdca; color: #b42318; padding: 9px 12px; border-radius: 8px; font-size: 13px; margin: 10px 0; }
.proof-notice { background: #ecfdf3; border: 1px solid #abefc6; color: #027a48; padding: 9px 12px; border-radius: 8px; font-size: 13px; margin: 10px 0; }
@media (max-width: 900px) { .context-grid, .result-grid, .receipt-grid { grid-template-columns: 1fr; } .wide { grid-column: auto; } }
</style>
