import { useEffect, useRef } from 'react'
import type { ChatCardActions } from '../cards/cardActions'
import { CaseStatusCard } from '../cards/CaseStatusCard'
import { ConfirmFieldsCard } from '../cards/ConfirmFieldsCard'
import { ContactsCard } from '../cards/ContactsCard'
import { DocumentChecklistCard } from '../cards/DocumentChecklistCard'
import { SalesDataUploadCard } from '../cards/SalesDataUploadCard'
import { FormModeCard } from '../cards/FormModeCard'
import { HandoffCard } from '../cards/HandoffCard'
import { MallPickerCard } from '../cards/MallPickerCard'
import { ReviewCard } from '../cards/ReviewCard'
import { SuccessCard } from '../cards/SuccessCard'
import { VerificationCard } from '../cards/VerificationCard'
import type { UiCard } from '../../types/contracts'
import styles from './CardSlot.module.css'

interface CardSlotProps {
  card: UiCard
  actions: ChatCardActions
  focusOnMount?: boolean
}

export function CardSlot({ card, actions, focusOnMount = false }: CardSlotProps) {
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!focusOnMount || !rootRef.current) return
    const focusable = rootRef.current.querySelector<HTMLElement>(
      'button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])',
    )
    focusable?.focus({ preventScroll: false })
  }, [focusOnMount, card.card_id])

  return (
    <div ref={rootRef} className={styles.slot} data-testid={`card-slot-${card.card_id}`}>
      {card.card_type === 'confirm_fields' ? (
        <ConfirmFieldsCard
          cardId={card.card_id}
          payload={card.payload}
          onConfirm={() => actions.sendAction('confirm_card', { card_id: card.card_id })}
        />
      ) : null}
      {card.card_type === 'mall_picker' ? (
        <MallPickerCard
          payload={card.payload}
          locked={actions.mallsConfirmed}
          onDone={(mallIds) => actions.sendAction('select_malls', { mall_ids: mallIds })}
        />
      ) : null}
      {card.card_type === 'verification' ? (
        <VerificationCard
          payload={card.payload}
          onVerifyEmail={(token) => actions.sendAction('verify_email', { token })}
          onResendEmailLink={() => actions.sendAction('resend_email_link', {})}
          onVerifyCode={(code) => actions.sendAction('submit_otp', { code })}
          onResendCode={() => actions.sendAction('resend_otp', {})}
        />
      ) : null}
      {card.card_type === 'document_upload' ? (
        <DocumentChecklistCard
          payload={card.payload}
          onUpload={actions.uploadDocument}
          onRemove={actions.removeDocument}
          onSetNumber={actions.setDocumentNumber}
          onResubmit={() => actions.sendAction('resubmit_documents', {})}
        />
      ) : null}
      {card.card_type === 'case_status' ? <CaseStatusCard payload={card.payload} /> : null}
      {card.card_type === 'contacts' ? (
        <ContactsCard
          payload={card.payload}
          onSubmit={() => actions.sendAction('submit_contacts', {})}
        />
      ) : null}
      {card.card_type === 'sales_data_upload' ? (
        <SalesDataUploadCard
          payload={card.payload}
          onUpload={actions.uploadDocument}
          onRemove={actions.removeDocument}
          onSubmit={() => actions.sendAction('submit_sales_data', {})}
        />
      ) : null}
      {card.card_type === 'review' ? (
        <ReviewCard
          payload={card.payload}
          onEditField={(key, value) => actions.editReviewField(key, value)}
          onSubmit={() => actions.sendAction('accept_and_submit', { terms_accepted: true })}
        />
      ) : null}
      {card.card_type === 'success' ? <SuccessCard payload={card.payload} /> : null}
      {card.card_type === 'form_mode' ? (
        <FormModeCard
          payload={card.payload}
          onCheckCr={(crNumber) => actions.sendAction('cr_check', { cr_number: crNumber })}
          onSkipCr={() => actions.sendAction('cr_skip', {})}
          onSaveField={(key, value) => actions.editReviewField(key, value)}
          onCallMe={() => actions.sendAction('request_handoff', { reason: 'model_unavailable' })}
        />
      ) : null}
      {card.card_type === 'handoff' ? <HandoffCard payload={card.payload} /> : null}
      {card.card_type === 'quick_replies' ? null : null}
    </div>
  )
}
