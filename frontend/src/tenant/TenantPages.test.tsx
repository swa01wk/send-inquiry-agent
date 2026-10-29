import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/tenant'
import { draftEmpty } from '../mocks/fixtures'
import { TenantHomePage } from './TenantHomePage'
import { TenantInquiriesPage } from './TenantInquiriesPage'
import { TenantOpportunitiesPage } from './TenantOpportunitiesPage'

const oasis: api.TenantSummary = {
  id: 'T-1001',
  company_name: 'Oasis Coffee Company',
  contact_name: 'Layla Hassan',
  brands: [{ id: 'TB-1', name: 'Oasis Coffee' }],
}
const alNoor: api.TenantSummary = {
  id: 'T-1002',
  company_name: 'Al Noor Retail Group',
  contact_name: 'Khalid Al Noor',
  brands: [
    { id: 'TB-2', name: 'Noor Fashion' },
    { id: 'TB-3', name: 'Noor Beauty' },
  ],
}
const opportunities: api.Opportunity[] = [
  {
    id: 'OPP-101',
    mall_id: 'riyadh-mall-a',
    mall: 'Riyadh Mall A',
    city_id: 'riyadh',
    city: 'Riyadh',
    unit_type: 'store',
    unit_type_label: 'Store',
    unit_ref: 'RMA-G-014',
    area_min: 80,
    area_max: 120,
  },
  {
    id: 'OPP-103',
    mall_id: 'jeddah-mall-b',
    mall: 'Jeddah Mall B',
    city_id: 'jeddah',
    city: 'Jeddah',
    unit_type: 'store',
    unit_type_label: 'Store',
    unit_ref: 'JMB-1-122',
    area_min: 150,
    area_max: 220,
  },
]

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<div>Chat home</div>} />
        <Route path="/tenant" element={<TenantHomePage />} />
        <Route path="/tenant/opportunities" element={<TenantOpportunitiesPage />} />
        <Route path="/tenant/inquiries" element={<TenantInquiriesPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Tenant Central (simulated)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.sessionStorage.clear()
    vi.spyOn(api, 'listTenants').mockResolvedValue([oasis, alNoor])
    vi.spyOn(api, 'listOpportunities').mockResolvedValue(opportunities)
  })

  it('signs in and lands on Leasing Opportunities', async () => {
    const user = userEvent.setup()
    renderAt('/tenant')
    await screen.findByRole('option', { name: /Oasis Coffee Company/ })
    await user.selectOptions(screen.getByLabelText('Company'), 'T-1001')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByTestId('tenant-signed-in')).toHaveTextContent('Oasis Coffee Company')
    expect(await screen.findByTestId('opportunity-OPP-101')).toBeInTheDocument()
  })

  it('signs in from ?as= (the dev landing page)', async () => {
    renderAt('/tenant?as=T-1001')
    expect(await screen.findByTestId('tenant-signed-in')).toHaveTextContent('Layla Hassan')
  })

  it('filters by city', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.tenantId', 'T-1001')
    renderAt('/tenant/opportunities')
    await screen.findByTestId('opportunity-OPP-103')
    await user.selectOptions(screen.getByLabelText('City'), 'jeddah')
    expect(screen.queryByTestId('opportunity-OPP-101')).not.toBeInTheDocument()
    expect(screen.getByTestId('opportunity-OPP-103')).toBeInTheDocument()
  })

  it('raises an inquiry and opens the chat', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.tenantId', 'T-1001')
    const raise = vi.spyOn(api, 'raiseInquiry').mockResolvedValue({
      session_id: 'tenant-session',
      messages: [{ id: 'tenant-1', role: 'assistant', text: 'Welcome back, Layla.' }],
      cards: [],
      draft: draftEmpty,
    })
    renderAt('/tenant/opportunities')
    const card = await screen.findByTestId('opportunity-OPP-103')
    await user.click(within(card).getByRole('button', { name: 'Raise inquiry' }))
    expect(raise).toHaveBeenCalledWith('T-1001', 'OPP-103', 'TB-1')
    expect(await screen.findByText('Chat home')).toBeInTheDocument()
  })

  it('lets a tenant with several brands choose one first', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.tenantId', 'T-1002')
    const raise = vi.spyOn(api, 'raiseInquiry').mockResolvedValue({
      session_id: 's',
      messages: [],
      cards: [],
      draft: draftEmpty,
    })
    renderAt('/tenant/opportunities')
    await user.selectOptions(await screen.findByLabelText('For brand'), 'TB-3')
    const card = screen.getByTestId('opportunity-OPP-101')
    await user.click(within(card).getByRole('button', { name: 'Raise inquiry' }))
    expect(raise).toHaveBeenCalledWith('T-1002', 'OPP-101', 'TB-3')
  })

  it('lists My inquiries with tracking links', async () => {
    window.sessionStorage.setItem('cenomi.tenantId', 'T-1001')
    vi.spyOn(api, 'listMyInquiries').mockResolvedValue([
      {
        reference: 'GEO-STR-123456',
        brand: 'Oasis Coffee',
        mall: 'Riyadh Mall A',
        product_line: 'Store',
        stage_label: 'First review',
        submitted_at: '2026-11-02T07:00:00.000Z',
        last_change: '2026-11-02T07:00:00.000Z',
        tracking_url: 'http://localhost:5173/inquiry/status/GEO-STR-123456?t=x',
      },
    ])
    renderAt('/tenant/inquiries')
    const table = await screen.findByTestId('my-inquiries')
    expect(within(table).getByRole('link', { name: 'GEO-STR-123456' })).toHaveAttribute(
      'href',
      'http://localhost:5173/inquiry/status/GEO-STR-123456?t=x',
    )
    expect(within(table).getByText('First review')).toBeInTheDocument()
  })

  it('asks for sign-in on a signed-in page', () => {
    renderAt('/tenant/inquiries')
    expect(screen.getByRole('link', { name: 'Sign in to Tenant Central' })).toBeInTheDocument()
  })
})
