import type { DraftFieldRow, ReviewGroupRow } from '../../types/contracts'

export const DRAFT_GROUP_ORDER = ['company', 'brand', 'space', 'contact'] as const

export type DraftGroupId = (typeof DRAFT_GROUP_ORDER)[number]

export type PanelFieldRow = DraftFieldRow & { phoneKind?: 'Mobile' | 'Landline' }

const GROUP_TITLES: Record<DraftGroupId, string> = {
  company: 'Company',
  brand: 'Brand',
  space: 'Space',
  contact: 'Contact',
}

export function draftGroupTitle(group: string): string {
  return GROUP_TITLES[group as DraftGroupId] ?? group
}

export function fieldsInPanelOrder(fields: DraftFieldRow[]): DraftFieldRow[] {
  return DRAFT_GROUP_ORDER.flatMap((group) => fields.filter((f) => f.group === group))
}

function contactFieldsForPanel(fields: DraftFieldRow[]): PanelFieldRow[] {
  const mobile = fields.find((f) => f.key === 'mobile')
  const landline = fields.find((f) => f.key === 'landline')
  const rest = fields.filter((f) => f.key !== 'mobile' && f.key !== 'landline')

  let phone: PanelFieldRow
  if (mobile?.display) {
    phone = { ...mobile, key: 'phone', label: 'Phone', phoneKind: 'Mobile' }
  } else if (landline?.display) {
    phone = { ...landline, key: 'phone', label: 'Phone', phoneKind: 'Landline' }
  } else {
    phone = {
      key: 'phone',
      label: 'Phone',
      group: 'contact',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    }
  }

  return [...rest, phone]
}

export function fieldsForDraftGroup(
  groupId: DraftGroupId,
  fields: DraftFieldRow[],
): PanelFieldRow[] {
  const inGroup = fields.filter((f) => f.group === groupId)
  if (groupId !== 'contact') return inGroup
  return contactFieldsForPanel(inGroup)
}

export function contactReviewRows(rows: ReviewGroupRow[]): ReviewGroupRow[] {
  const mobile = rows.find((r) => r.key === 'mobile')
  const landline = rows.find((r) => r.key === 'landline')
  const rest = rows.filter((r) => r.key !== 'mobile' && r.key !== 'landline')

  let phone: ReviewGroupRow
  if (mobile?.display) {
    phone = { ...mobile, key: 'phone', label: 'Phone' }
  } else if (landline?.display) {
    phone = { ...landline, key: 'phone', label: 'Phone' }
  } else {
    phone = {
      key: 'phone',
      label: 'Phone',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    }
  }

  return [...rest, phone]
}

export function firstChangedKeyInPanelOrder(
  fields: DraftFieldRow[],
  changedKeys: string[],
): string | null {
  if (changedKeys.length === 0) return null
  const changed = new Set(changedKeys)
  const ordered = fieldsInPanelOrder(fields)
  const hit = ordered.find((f) => changed.has(f.key))
  return hit?.key ?? null
}
