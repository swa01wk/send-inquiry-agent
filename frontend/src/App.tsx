import { InquiryLayout } from './components/layout/InquiryLayout'
import { PageShell } from './components/layout/PageShell'
import { ChatProvider } from './state/chatStore'

function App() {
  return (
    <PageShell>
      <ChatProvider>
        <InquiryLayout />
      </ChatProvider>
    </PageShell>
  )
}

export default App
