import { describe, expect, it } from 'vitest'
import { draftComplete, draftEmpty, draftMidway } from '../../mocks/fixtures'
import type { DraftSummary } from '../../types/contracts'
import {
  currentProgressStage,
  documentsStageDone,
  stageIsDone,
  stageVisualState,
} from './inquiryProgress'

function draftWithChecks(
  patch: Partial<DraftSummary['checks']>,
  base = draftComplete,
): DraftSummary {
  return { ...base, checks: { ...base.checks, ...patch } }
}

describe('inquiryProgress', () => {
  it('marks documents done while contact verification is still pending', () => {
    const draft = draftWithChecks({
      contact_verified: false,
      email_verified: false,
      mobile_verified: true,
      required_docs_uploaded: 2,
      required_docs_total: 2,
      remaining: ['verify_email', 'terms'],
      next_step: 'verify_email',
    })
    expect(documentsStageDone(draft)).toBe(true)
    expect(stageIsDone('documents', 'verifying', draft)).toBe(true)
    expect(currentProgressStage('verifying', draft)).toBe('contact')
  })

  it('keeps documents ticked after a post-verification field correction', () => {
    const draft = draftWithChecks({
      unconfirmed: 1,
      remaining: ['fields', 'terms'],
      next_step: 'fields',
    })
    draft.fields = draft.fields.map((f) =>
      f.key === 'unit_type' ? { ...f, confirmed: false, source: 'user' } : f,
    )
    expect(documentsStageDone(draft)).toBe(true)
    expect(stageIsDone('documents', 'collecting', draft)).toBe(true)
  })

  it('uses next_step for the current tab', () => {
    const draft = draftWithChecks({
      next_step: 'verify_email',
      remaining: ['verify_email', 'terms'],
      contact_verified: false,
      email_verified: false,
      mobile_verified: false,
      required_docs_uploaded: 0,
    })
    expect(stageVisualState('contact', 'verifying', draft)).toBe('current')
    expect(stageVisualState('documents', 'verifying', draft)).toBe('upcoming')
  })

  it('marks gate with CR as company current', () => {
    expect(currentProgressStage('gate', draftEmpty)).toBe('company')
    expect(stageVisualState('company', 'gate', draftEmpty)).toBe('current')
  })

  it('derives fields step to the first group with a gap', () => {
    expect(currentProgressStage('collecting', draftMidway)).toBe('company')
  })
})
