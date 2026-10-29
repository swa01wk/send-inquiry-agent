import type { ReviewerSuggestionPayload } from '../types/contracts'
import type { ActionsPrefill } from './ActionsPanel'
import type { YardiCompany } from '../api/review'

export function prefillFromSuggestion(payload: ReviewerSuggestionPayload): ActionsPrefill {
  const token = Date.now()
  switch (payload.action) {
    case 'reject':
      return { token, rejectRemarks: String(payload.payload.remarks ?? '') }
    case 'request_reupload':
      return { token, reuploadRemarks: String(payload.payload.remarks ?? '') }
    case 'request_contacts':
      return { token, requestRemarks: String(payload.payload.remarks ?? '') }
    case 'relink_company': {
      const companyId = String(payload.payload.company_id ?? '')
      const nameMatch = payload.text.match(/^(.+?)\s+\(id\s/)
      const name = nameMatch?.[1]?.trim() ?? companyId
      const companies: YardiCompany[] = [{ id: companyId, name }]
      return { token, yardiCompanies: companies, yardiCompanyId: companyId }
    }
    case 'relink_brand':
      return { token, yardiBrandId: String(payload.payload.brand_id ?? '') }
    default:
      return { token }
  }
}
