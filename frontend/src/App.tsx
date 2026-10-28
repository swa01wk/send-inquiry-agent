import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DEV_TOOLS, REVIEWER_CONSOLE } from './config'
import { ChatHomePage } from './pages/ChatHomePage'
import { DevInboxPage } from './pages/DevInboxPage'
import { InquiryStatusPage } from './pages/InquiryStatusPage'
import { VerifyPage } from './pages/VerifyPage'
import { ReviewCasePage } from './review/ReviewCasePage'
import { ReviewQueuePage } from './review/ReviewQueuePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatHomePage />} />
        <Route path="/inquiry/verify" element={<VerifyPage />} />
        <Route path="/inquiry/status/:reference" element={<InquiryStatusPage />} />
        {DEV_TOOLS ? <Route path="/dev/inbox" element={<DevInboxPage />} /> : null}
        {DEV_TOOLS ? null : <Route path="/dev/inbox" element={<Navigate to="/" replace />} />}
        {REVIEWER_CONSOLE ? <Route path="/review" element={<ReviewQueuePage />} /> : null}
        {REVIEWER_CONSOLE ? (
          <Route path="/review/cases/:reference" element={<ReviewCasePage />} />
        ) : null}
      </Routes>
    </BrowserRouter>
  )
}

export default App
