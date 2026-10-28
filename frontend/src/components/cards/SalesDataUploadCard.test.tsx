import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SalesDataPayload } from '../../types/contracts'
import { SalesDataUploadCard } from './SalesDataUploadCard'

const sample: SalesDataPayload = {
  request_id: 'req-sales',
  remarks: 'Please share estimated monthly sales.',
  uploaded: false,
  file_name: null,
  size_bytes: null,
  allowed_extensions: ['.pdf', '.xlsx'],
  max_mb: 5,
}

describe('SalesDataUploadCard', () => {
  it('uploads with doc_type sales_data and enables send when uploaded', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockResolvedValue(undefined)
    const onSubmit = vi.fn()

    const { rerender } = render(
      <SalesDataUploadCard
        payload={sample}
        onUpload={onUpload}
        onRemove={async () => undefined}
        onSubmit={onSubmit}
      />,
    )

    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /upload/i }))
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ok = new File(['x'], 'sales.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    await user.upload(input, ok)
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith('sales_data', ok))

    rerender(
      <SalesDataUploadCard
        payload={{
          ...sample,
          uploaded: true,
          file_name: 'sales.xlsx',
          size_bytes: 1,
        }}
        onUpload={onUpload}
        onRemove={async () => undefined}
        onSubmit={onSubmit}
      />,
    )

    await user.click(screen.getByRole('button', { name: /^send$/i }))
    expect(onSubmit).toHaveBeenCalled()
  })
})
