import type { DraftFieldRow } from '../../types/contracts'

export const DRAFT_GROUP_ORDER = ['company', 'brand', 'space', 'contact'] as const

export type DraftGroupId = (typeof DRAFT_GROUP_ORDER)[number]

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
