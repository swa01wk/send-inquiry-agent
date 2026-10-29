import type { AttentionItem, AttentionList, CaseDetail, QueueItem, Reviewer } from '../api/review'

/** Test fixtures for the reviewer console (shapes from `docs/spec.md` §13). */

export const reviewerCentral: Reviewer = {
  id: 'rlm_store-central',
  name: 'Faisal Al Qahtani',
  role: 'rlm_store',
  regions: ['central'],
  manager: false,
}

export const queueItem: QueueItem = {
  reference: 'GEO-STR-123456',
  brand: 'Bean Street',
  company: 'Bean Street Trading Co.',
  mall: 'Riyadh Mall A',
  product_line: 'store',
  region: 'central',
  status: 'first_review',
  stage_label: 'First review',
  waiting_on: 'reviewer',
  age_days: 0.2,
  last_change: '2026-10-28T09:00:00.000Z',
  open_requests: [],
  possible_duplicate: false,
  follow_on_of: null,
  needs_operations: false,
}

export function caseDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  return {
    brief: {
      reference: 'GEO-STR-123456',
      status: 'first_review',
      stage_label: 'First review',
      waiting_on: 'reviewer',
      queue_role: 'rlm_store',
      queue_region: 'central',
      channel: 'chat',
      company: 'Bean Street Trading Co.',
      brand: 'Bean Street',
      product_line: 'store',
      mall: 'Riyadh Mall A',
      region: 'central',
      cr_status: 'verified',
      submitted_at: '2026-10-28T09:00:00.000Z',
      fields: [
        {
          key: 'company_name',
          label: 'Company name',
          group: 'company',
          display: 'Bean Street Trading Co.',
          source: 'verified',
          confirmed: true,
          evidence: null,
        },
        {
          key: 'brand_category',
          label: 'Brand category',
          group: 'brand',
          display: 'Coffee',
          source: 'derived',
          confirmed: true,
          evidence: 'we sell specialty coffee',
        },
      ],
      verification: { email_verified: true, mobile_verified: true },
      documents: [
        {
          doc_type: 'cr_certificate',
          label: 'CR certificate',
          required: true,
          uploaded: true,
          file_id: 'file_1',
          file_name: 'cr.pdf',
          size_bytes: 1200,
          uploaded_at: '2026-10-28T08:55:00.000Z',
          replaced_versions: 0,
        },
      ],
      sales_data: null,
      contacts: [],
      requests: [],
      decisions: [],
      follow_on_of: null,
      yardi: {
        company_id: null,
        brand_id: null,
        lead_ref: null,
        attempts: 0,
        needs_operations: false,
      },
      stage_ages: [],
      next_decision_checklist: ['Check the CR certificate matches the company name'],
    },
    timeline: [
      {
        at: '2026-10-28T09:00:00.000Z',
        actor: 'system',
        type: 'case_transition',
        summary: 'Routed to Regional Leasing Manager (Store), Central',
      },
    ],
    legal_actions: ['request_reupload', 'reject', 'approve_first'],
    approval_blockers: [],
    rejection_categories: ['incomplete_documents', 'not_a_fit', 'no_space', 'other'],
    reupload_doc_types: [
      { doc_type: 'cr_certificate', label: 'CR certificate' },
      { doc_type: 'vat_certificate', label: 'VAT certificate' },
    ],
    ...overrides,
  }
}

/** A second-review case: contacts in, a Yardi company to link. */
export function secondReviewDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  const base = caseDetail()
  return {
    ...base,
    brief: {
      ...base.brief,
      status: 'second_review',
      stage_label: 'Lead — second review',
      contacts: [
        {
          role: 'billing_contact',
          label: 'Billing Contact',
          name: 'Omar Saleh',
          email: 'omar@beanstreet.example',
          phone: '+966551234567',
          same_as_primary: false,
        },
      ],
    },
    legal_actions: [
      'request_sales_data',
      'relink_company',
      'relink_brand',
      'remove_contact',
      'reject',
    ],
    approval_blockers: ['missing_contact:authorized_signatory', 'open_request:contacts'],
    ...overrides,
  }
}

export function stalledItem(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return {
    id: 'att_stalled1',
    trigger: 'stalled_review',
    label: 'Review is taking longer than the target',
    recommended: 'Open the case and make the next decision.',
    reference: 'GEO-STR-123456',
    brand: 'Bean Street',
    mall: 'Riyadh Mall A',
    stage_label: 'First review',
    status: 'open',
    audience: 'queue',
    tier: 0,
    age_hours: 49.2,
    threshold_hours: 48,
    request_kind: null,
    request_label: null,
    text: null,
    raised_at: '2026-10-30T09:00:00.000Z',
    send_after: null,
    sent_at: null,
    dismissed_reason: null,
    ...overrides,
  }
}

export function reminderItem(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return stalledItem({
    id: 'att_reminder1',
    trigger: 'applicant_reminder',
    label: 'Request unanswered — reminder drafted',
    recommended: 'Approve and send the reminder, edit it, or dismiss it.',
    stage_label: 'Lead — second review',
    status: 'awaiting_approval',
    tier: 2,
    age_hours: 73,
    threshold_hours: 72,
    request_kind: 'contacts',
    request_label: 'Add company contacts',
    text: 'The leasing team is still waiting for your company contacts on your inquiry GEO-STR-123456.',
    ...overrides,
  })
}

export function attentionList(items: AttentionItem[]): AttentionList {
  return {
    items,
    counts: { open: items.length, raised: items.length, sent: 0, dismissed: {} },
    dismiss_reasons: ['not_needed', 'already_handled', 'applicant_contacted', 'other'],
  }
}
