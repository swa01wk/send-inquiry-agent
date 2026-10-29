import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DEV_TOOLS, REVIEWER_CONSOLE } from './config'
import { CasePage } from './pages/CasePage'
import { ChatHomePage } from './pages/ChatHomePage'
import { DevHomePage } from './pages/DevHomePage'
import { DevInboxPage } from './pages/DevInboxPage'
import { InquiryStatusPage } from './pages/InquiryStatusPage'
import { VerifyPage } from './pages/VerifyPage'
import { AttentionPage } from './review/AttentionPage'
import { ReviewCasePage } from './review/ReviewCasePage'
import { ReviewQueuePage } from './review/ReviewQueuePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatHomePage />} />
        <Route path="/inquiry/verify" element={<VerifyPage />} />
        <Route path="/inquiry/case" element={<CasePage />} />
        <Route path="/inquiry/status/:reference" element={<InquiryStatusPage />} />
        {DEV_TOOLS ? <Route path="/dev" element={<DevHomePage />} /> : null}
        {DEV_TOOLS ? <Route path="/dev/inbox" element={<DevInboxPage />} /> : null}
        {DEV_TOOLS ? null : <Route path="/dev/inbox" element={<Navigate to="/" replace />} />}
        {REVIEWER_CONSOLE ? <Route path="/review" element={<ReviewQueuePage />} /> : null}
        {REVIEWER_CONSOLE ? (
          <Route path="/review/cases/:reference" element={<ReviewCasePage />} />
        ) : null}
        {REVIEWER_CONSOLE ? <Route path="/review/attention" element={<AttentionPage />} /> : null}
      </Routes>
    </BrowserRouter>
  )
}

export default App
