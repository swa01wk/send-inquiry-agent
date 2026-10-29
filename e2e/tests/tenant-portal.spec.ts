import { expect, test } from '@playwright/test'

/** Day 5 intake channels: an existing tenant raises an inquiry from Leasing Opportunities. */
test.describe('Tenant Central (existing tenant) @scripted', () => {
  test('sign in from /dev, filter opportunities, raise an inquiry prefilled and verified', async ({
    page,
  }) => {
    await page.goto('/dev')
    await page
      .getByTestId('dev-tenants')
      .getByRole('link', { name: /Oasis Coffee Company/ })
      .click()
    await expect(page.getByTestId('tenant-signed-in')).toContainText('Oasis Coffee Company')

    await page.getByLabel('City').selectOption('jeddah')
    await expect(page.getByTestId('opportunity-OPP-101')).toHaveCount(0)
    const unit = page.getByTestId('opportunity-OPP-103')
    await expect(unit).toContainText('Jeddah Mall B')
    await unit.getByRole('button', { name: 'Raise inquiry' }).click()

    // The chat opens in existing-tenant mode: greeted by name, details from the record.
    await expect(page.getByText(/Welcome back, Layla/)).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/Oasis Coffee Company's details/)).toBeVisible()

    await page.goto('/tenant/inquiries')
    await expect(page.getByTestId('my-inquiries-empty')).toBeVisible()
  })
})
