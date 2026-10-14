import { useEffect, useRef } from 'react'
import type { ChatCardActions } from '../cards/cardActions'
import { ConfirmFieldsCard } from '../cards/ConfirmFieldsCard'
import { DocumentChecklistCard } from '../cards/DocumentChecklistCard'
import { MallPickerCard } from '../cards/MallPickerCard'
import { OtpCard } from '../cards/OtpCard'
import { ReviewCard } from '../cards/ReviewCard'
import { SuccessCard } from '../cards/SuccessCard'
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
    <div
      ref={rootRef}
      className={styles.slot}
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
      {card.card_type === 'otp_input' ? (
        <OtpCard
          payload={card.payload}
          onVerify={(code) => actions.sendAction('submit_otp', { code })}
          onResend={() => actions.sendAction('resend_otp', {})}
        />
      ) : null}
      {card.card_type === 'document_upload' ? (
        <DocumentChecklistCard
          payload={card.payload}
          onUpload={actions.uploadDocument}
          onRemove={actions.removeDocument}
        />
      ) : null}
      {card.card_type === 'review' ? (
        <ReviewCard
          payload={card.payload}
          onEditField={(key, value) => actions.sendAction('edit_field', { key, value })}
          onSubmit={() => actions.sendAction('accept_and_submit', { terms_accepted: true })}
        />
      ) : null}
      {card.card_type === 'success' ? (
        <SuccessCard payload={card.payload} />
      ) : null}
      {card.card_type === 'quick_replies' ? null : null}
    </div>
  )
}
