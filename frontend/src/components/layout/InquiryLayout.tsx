import { useState } from 'react'
import { ChatPanel } from '../chat/ChatPanel'
import { DraftPanel } from '../draft/DraftPanel'

export function InquiryLayout() {
  const [draftVisible, setDraftVisible] = useState(true)

  return (
    <>
      <ChatPanel
        draftPanelVisible={draftVisible}
        onToggleDraftPanel={() => setDraftVisible((v) => !v)}
      />
      {draftVisible ? <DraftPanel /> : null}
    </>
  )
}
