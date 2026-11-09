import { expect, test } from '@playwright/test'

/** Day 5 intake channels: an existing tenant raises an inquiry from Leasing Opportunities. */
test.describe('Tenant Central (existing tenant) @scripted', () => {
  test('sign in from /dev, filter opportunities, raise an inquiry prefilled and verified', async ({
    page,
  }) => {
    // Raising opens a draft only: My inquiries lists submitted inquiries, so its count stays
    // the same (other stories in the run may already have submitted for Oasis).
    const mine = async () =>
      (
        (await (
          await page.request.get('http://127.0.0.1:8000/api/tenant/inquiries', {
            headers: { 'X-Tenant-Id': 'T-1001' },
          })
        ).json()) as unknown[]
      ).length
    const before = await mine()

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

    // The chat opens in existing-tenant mode: greeted by name, the company from the Cenomi
    // record (Yardi by CR), and asked for the new brand (R4, demo feedback §3.8).
    // The sr-only live region repeats the same text for screen readers.
    const greeting = page.getByTestId('bot-bubble-text').filter({ hasText: /Welcome back, Layla/ })
    await expect(greeting).toBeVisible({ timeout: 30_000 })
    await expect(greeting).toContainText("Oasis Coffee Company's details from your Cenomi record")
    await expect(greeting).toContainText('new brand')

    await page.goto('/tenant/inquiries')
    await expect(
      page.getByTestId(before === 0 ? 'my-inquiries-empty' : 'my-inquiries'),
    ).toBeVisible()
    expect(await mine()).toBe(before)
  })
})
