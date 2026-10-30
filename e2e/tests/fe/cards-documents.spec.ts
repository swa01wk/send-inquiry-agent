import { expect, test } from '@playwright/test'
import path from 'node:path'
import { FeInquiryPage, feFixtures } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Documents card @fe', () => {
  test('partial state shows required rows', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('documents-partial')
    await expect(inquiry.cards('document_upload')).toBeVisible()
    await expect(page.getByTestId('doc-row-company_profile')).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('complete state shows uploaded files', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('documents-complete')
    await expect(page.getByTestId('doc-row-company_profile')).toContainText(/BeanStreet/i)
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('on_file row shows on file status', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('documents-on-file')
    const row = page.getByTestId('doc-row-company_profile')
    await expect(row.getByTestId('doc-status')).toContainText(/on file/i)
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('upload sends mock request path', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('documents-partial')
    const row = page.getByTestId('doc-row-company_profile')
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      row.getByRole('button', { name: 'Upload' }).click(),
    ])
    await fileChooser.setFiles(path.join(feFixtures, 'company_profile.pdf'))
    await expect(row.getByTestId('doc-status')).toContainText(/company_profile\.pdf/i, {
      timeout: 15_000,
    })
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
