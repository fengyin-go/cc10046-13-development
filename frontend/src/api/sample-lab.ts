import { request } from './client'

export type LabScalar = string | number | boolean | null
export type LabRecord = Record<string, any>

async function postJson<T = LabRecord>(path: string, body: LabRecord = {}): Promise<T> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail || `接口返回 ${response.status}`)
  }
  return data as T
}

async function getJson<T = LabRecord>(path: string): Promise<T> {
  const response = await request(path)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail || `接口返回 ${response.status}`)
  }
  return data as T
}

export const sampleLabApi = {
  state: () => getJson('/api/template-lab/state'),
  compare: (body: LabRecord) => postJson('/api/template-lab/diffs', body),
  diff: (id: string) => getJson(`/api/template-lab/diffs/${encodeURIComponent(id)}`),
  selectDiff: (id: string) => postJson(`/api/template-lab/diffs/${encodeURIComponent(id)}/select`),
  correctSource: (sampleId: string, body: LabRecord) =>
    postJson(`/api/template-lab/samples/${encodeURIComponent(sampleId)}/correct-source`, body),
  refreshConfirm: (sampleId: string) =>
    postJson(`/api/template-lab/samples/${encodeURIComponent(sampleId)}/refresh-confirm`),
  fieldContext: () => getJson('/api/template-lab/field-context'),
  trial: (body: LabRecord) => postJson('/api/field-mapper/trial', body),
  submitProofread: (body: LabRecord) => postJson('/api/field-mapper/proofread', body),
}
