import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DEV_TOOLS } from './config'
import { ChatHomePage } from './pages/ChatHomePage'
import { DevInboxPage } from './pages/DevInboxPage'
import { InquiryStatusPage } from './pages/InquiryStatusPage'
import { VerifyPage } from './pages/VerifyPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatHomePage />} />
        <Route path="/inquiry/verify" element={<VerifyPage />} />
        <Route path="/inquiry/status/:reference" element={<InquiryStatusPage />} />
        {DEV_TOOLS ? <Route path="/dev/inbox" element={<DevInboxPage />} /> : null}
        {DEV_TOOLS ? null : <Route path="/dev/inbox" element={<Navigate to="/" replace />} />}
      </Routes>
    </BrowserRouter>
  )
}

export default App
