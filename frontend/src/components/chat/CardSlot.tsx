import { useEffect, useRef } from 'react'
import type { ChatCardActions } from '../cards/cardActions'
import { CaseStatusCard } from '../cards/CaseStatusCard'
import { ConfirmFieldsCard } from '../cards/ConfirmFieldsCard'
import { ContactsCard } from '../cards/ContactsCard'
import { DocumentChecklistCard } from '../cards/DocumentChecklistCard'
import { SalesDataUploadCard } from '../cards/SalesDataUploadCard'
import { FormModeCard } from '../cards/FormModeCard'
import { BasicInfoReviewCard } from '../cards/BasicInfoReviewCard'
import { CrQuestionCard } from '../cards/CrQuestionCard'
import { CompanyRegistrationCard } from '../cards/CompanyRegistrationCard'
import { TermsCard } from '../cards/TermsCard'
import { SignatoryQuestionCard } from '../cards/SignatoryQuestionCard'
import { ContactCheckCard } from '../cards/ContactCheckCard'
import { InformTenantCard } from '../cards/InformTenantCard'
import { HandoffCard } from '../cards/HandoffCard'
import { SendLinkCard } from '../cards/SendLinkCard'
import { SignInPromptCard } from '../cards/SignInPromptCard'
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
  highlighted?: boolean
}

export function CardSlot({
  card,
  actions,
  focusOnMount = false,
  highlighted = false,
}: CardSlotProps) {
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!focusOnMount || !rootRef.current) return
    const focusable = rootRef.current.querySelector<HTMLElement>(
      'button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])',
    )
    focusable?.focus({ preventScroll: false })
  }, [focusOnMount, card.card_id])

  return (
    <div
      ref={rootRef}
      className={`${styles.slot}${highlighted ? ` ${styles.highlight}` : ''}`}
      data-testid={`card-slot-${card.card_id}`}
    >
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
          demoLinkWaiting={
            actions.isActionQueued?.('verify_email', {
              token: card.payload.email.demo_token ?? '',
            }) ?? false
          }
        />
      ) : null}
      {card.card_type === 'document_upload' ? (
        <DocumentChecklistCard
          payload={card.payload}
          filledFieldsByDocType={actions.documentFilledFields}
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
      {card.card_type === 'basic_info_review' ? (
        <BasicInfoReviewCard
          payload={card.payload}
          onEditField={(key, value) => actions.sendAction('edit_field', { key, value })}
          onProceed={() => actions.sendAction('proceed_basic_info', {})}
        />
      ) : null}
      {card.card_type === 'send_link' ? (
        <SendLinkCard
          payload={card.payload}
          onSendLink={() => actions.sendAction('send_application_link', {})}
        />
      ) : null}
      {card.card_type === 'contact_check' ? (
        <ContactCheckCard
          payload={card.payload}
          onCheck={(email) => actions.sendAction('contact_check', { email })}
        />
      ) : null}
      {card.card_type === 'inform_tenant' ? (
        <InformTenantCard
          payload={card.payload}
          onSendSignInLink={() => actions.sendAction('send_sign_in_link', {})}
        />
      ) : null}
      {card.card_type === 'cr_question' ? (
        <CrQuestionCard
          payload={card.payload}
          onAnswer={(hasCr) => actions.sendAction('cr_answer', { has_cr: hasCr })}
        />
      ) : null}
      {card.card_type === 'company_registration' ? (
        <CompanyRegistrationCard
          payload={card.payload}
          onVerify={(crNumber) => actions.sendAction('cr_check', { cr_number: crNumber })}
          onSkip={() => actions.sendAction('cr_skip', {})}
          onConfirmSkip={() => actions.sendAction('cr_skip', { confirmed: true })}
          onDismissSkipConfirm={() => undefined}
        />
      ) : null}
      {card.card_type === 'terms' ? (
        <TermsCard
          payload={card.payload}
          onAccept={() => actions.postAcceptTerms?.() ?? Promise.resolve(true)}
        />
      ) : null}
      {card.card_type === 'signatory_question' ? (
        <SignatoryQuestionCard
          payload={card.payload}
          onAnswer={(isSignatory) =>
            actions.sendAction('signatory_answer', { is_signatory: isSignatory })
          }
        />
      ) : null}
      {card.card_type === 'sign_in_prompt' ? <SignInPromptCard payload={card.payload} /> : null}
      {card.card_type === 'quick_replies' ? null : null}
    </div>
  )
}
