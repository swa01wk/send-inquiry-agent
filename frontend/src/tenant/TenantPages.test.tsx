import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/tenant'
import { TenantHomePage } from './TenantHomePage'
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
    // 18 Nov: the card shows the mall, city and product line only, no unit code or area.
    expect(screen.getByTestId('opportunity-OPP-103')).not.toHaveTextContent('JMB-1-122')
    expect(screen.getByTestId('opportunity-OPP-103')).not.toHaveTextContent(/sqm/)
    // Chart S3: Leasing Opportunities is where sign-in lands; no inquiry is raised here.
    expect(screen.queryByRole('button', { name: 'Raise inquiry' })).not.toBeInTheDocument()
  })

  it('asks for sign-in on a signed-in page', () => {
    renderAt('/tenant/opportunities')
    expect(screen.getByRole('link', { name: 'Sign in to Tenant Central' })).toBeInTheDocument()
  })
})
