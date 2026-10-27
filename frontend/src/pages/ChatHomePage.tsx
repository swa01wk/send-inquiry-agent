import { useLocation } from 'react-router-dom'
import { InquiryLayout } from '../components/layout/InquiryLayout'
import { PageShell } from '../components/layout/PageShell'
import { ChatProvider } from '../state/chatStore'
import type { CreateSessionResponse } from '../types/contracts'

export function ChatHomePage() {
  const location = useLocation()
  const resumed = (location.state as { resumed?: CreateSessionResponse } | null)?.resumed ?? null

  return (
    <PageShell>
      <ChatProvider key={resumed?.session_id ?? 'new'} initialSession={resumed}>
        <InquiryLayout />
      </ChatProvider>
    </PageShell>
  )
}
