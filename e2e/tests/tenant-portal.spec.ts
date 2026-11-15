import { expect, test } from '@playwright/test'

/**
 * Tenant Central, simulated: where a registered company lands after "Customer already
 * registered. Please login" (chart S3, M13). Leasing Opportunities lists the units; raising
 * an inquiry from here (R4) isn't on the chart, so there's no Raise inquiry button.
 */
test.describe('Tenant Central (sign-in landing) @scripted', () => {
  test('sign in from /dev and land on Leasing Opportunities', async ({ page }) => {
    await page.goto('/dev')
    await page
      .getByTestId('dev-tenants')
      .getByRole('link', { name: /Oasis Coffee Company/ })
      .click()
    await expect(page.getByTestId('tenant-signed-in')).toContainText('Oasis Coffee Company')
    await expect(page.getByRole('heading', { name: /leasing opportunities/i })).toBeVisible()

    await page.getByLabel('City').selectOption('jeddah')
    await expect(page.getByTestId('opportunity-OPP-101')).toHaveCount(0)
    const unit = page.getByTestId('opportunity-OPP-103')
    await expect(unit).toContainText('Jeddah Mall B')
    await expect(page.getByRole('button', { name: 'Raise inquiry' })).toHaveCount(0)
  })
})
