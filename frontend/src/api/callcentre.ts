import { API_BASE } from '../config'

/** Call-centre console (spec §15). The `/callcentre` page itself is Day 5 part B. */

export interface StaffMember {
  id: string
  name: string
  role: 'customer_care' | 'guest_service' | string
  role_label: string
}

export async function listStaff(): Promise<StaffMember[]> {
  const res = await fetch(`${API_BASE}/api/callcentre/staff`)
  if (!res.ok) throw new Error(`staff failed (${res.status})`)
  return res.json() as Promise<StaffMember[]>
}
