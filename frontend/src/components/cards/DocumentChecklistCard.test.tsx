import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { documentUploadCardExample } from '../../mocks/fixtures'
import { DocumentChecklistCard } from './DocumentChecklistCard'

describe('DocumentChecklistCard', () => {
  it('rejects oversize and bad extension without upload', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn()
    if (documentUploadCardExample.card_type !== 'document_upload') throw new Error('bad fixture')

    render(
      <DocumentChecklistCard
        payload={documentUploadCardExample.payload}
        onUpload={onUpload}
        onRemove={async () => undefined}
        onSetNumber={() => undefined}
      />,
    )

    const uploadButtons = screen.getAllByRole('button', { name: /upload/i })
    await user.click(uploadButtons[0])

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const big = new File([new ArrayBuffer(6 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' })
    await user.upload(input, big)
    expect(await screen.findByText(/over 5 MB/i)).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()

    await user.click(uploadButtons[0])
    const bad = new File(['x'], 'virus.exe', { type: 'application/octet-stream' })
    fireEvent.change(input, { target: { files: [bad] } })
    expect(await screen.findByText(/file type isn't supported/i)).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('calls upload for valid file', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockResolvedValue(undefined)
    if (documentUploadCardExample.card_type !== 'document_upload') throw new Error('bad fixture')

    render(
      <DocumentChecklistCard
        payload={documentUploadCardExample.payload}
        onUpload={onUpload}
        onRemove={async () => undefined}
        onSetNumber={() => undefined}
      />,
    )

    await user.click(screen.getAllByRole('button', { name: /upload/i })[0])
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ok = new File(['pdf'], 'doc.pdf', { type: 'application/pdf' })
    await user.upload(input, ok)
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith('company_profile', ok))
  })

  it('shows read-only CR number next to CR certificate row', () => {
    if (documentUploadCardExample.card_type !== 'document_upload') throw new Error('bad fixture')
    const payload = {
      ...documentUploadCardExample.payload,
      numbers: [
        {
          key: 'cr_number',
          label: 'CR number',
          value: '1010123456',
          editable: false,
        },
      ],
    }
    render(
      <DocumentChecklistCard
        payload={payload}
        onUpload={async () => undefined}
        onRemove={async () => undefined}
        onSetNumber={() => undefined}
      />,
    )
    const crInput = screen.getByTestId('doc-number-cr_number')
    expect(crInput).toHaveAttribute('readonly')
    expect(crInput).toHaveValue('1010123456')
  })
})
