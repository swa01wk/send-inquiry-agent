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

  it('re-upload mode shows remarks, filters docs, and resubmits when complete', async () => {
    const user = userEvent.setup()
    const onResubmit = vi.fn()
    if (documentUploadCardExample.card_type !== 'document_upload') throw new Error('bad fixture')

    const payload = {
      ...documentUploadCardExample.payload,
      mode: 'reupload' as const,
      requested_doc_types: ['brand_profile'],
      remarks: 'Please upload a clearer brand profile.',
      docs: [
        {
          doc_type: 'brand_profile',
          label: 'Brand profile',
          required: true,
          uploaded: true,
          file_name: 'brand.pdf',
          size_bytes: 1000,
          on_file: false,
        },
        {
          doc_type: 'company_profile',
          label: 'Company profile',
          required: true,
          uploaded: false,
          file_name: null,
          size_bytes: null,
          on_file: false,
        },
      ],
      required_uploaded: 1,
      required_total: 1,
      numbers: [],
    }

    render(
      <DocumentChecklistCard
        payload={payload}
        onUpload={async () => undefined}
        onRemove={async () => undefined}
        onSetNumber={() => undefined}
        onResubmit={onResubmit}
      />,
    )

    expect(screen.getByTestId('document-checklist-card')).toHaveAttribute('data-mode', 'reupload')
    expect(screen.getByText('Please upload a clearer brand profile.')).toBeInTheDocument()
    expect(screen.getByText('Brand profile')).toBeInTheDocument()
    expect(screen.queryByText('Company profile')).not.toBeInTheDocument()
    expect(screen.queryByTestId('doc-number-cr_number')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /resubmit/i }))
    expect(onResubmit).toHaveBeenCalled()
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

  it('shows On file and Replace for tenant documents on file', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockResolvedValue(undefined)
    if (documentUploadCardExample.card_type !== 'document_upload') throw new Error('bad fixture')

    const payload = {
      ...documentUploadCardExample.payload,
      docs: [
        {
          doc_type: 'company_profile',
          label: 'Company Profile',
          required: true,
          uploaded: true,
          file_name: 'on-record.pdf',
          size_bytes: 500,
          on_file: true,
        },
      ],
      required_uploaded: 1,
      required_total: 1,
    }

    render(
      <DocumentChecklistCard
        payload={payload}
        onUpload={onUpload}
        onRemove={async () => undefined}
        onSetNumber={() => undefined}
      />,
    )

    expect(screen.getByText('On file')).toBeInTheDocument()
    expect(screen.queryByText(/Uploaded ·/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /replace/i }))
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ok = new File(['pdf'], 'new.pdf', { type: 'application/pdf' })
    await user.upload(input, ok)
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith('company_profile', ok))
  })
})
