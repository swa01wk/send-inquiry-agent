export type DraftFieldRow = {
  key: string
  display: string | null
  source: string | null
  confirmed: boolean
}

export function draftFields(draft: Record<string, unknown>): DraftFieldRow[] {
  return (draft.fields ?? []) as DraftFieldRow[]
}

export function fieldDisplay(draft: Record<string, unknown>, key: string): string | null {
  return draftFields(draft).find((f) => f.key === key)?.display ?? null
}

export function fieldSource(draft: Record<string, unknown>, key: string): string | null {
  return draftFields(draft).find((f) => f.key === key)?.source ?? null
}
