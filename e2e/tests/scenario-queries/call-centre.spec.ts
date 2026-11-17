import { expect, test } from '@playwright/test'
import { readDoneEventCount } from '../../support/events'
import {
  B,
  BOTH,
  LIVE,
  LIVE_ONLY,
  SARA,
  Tester,
  expectNoInboxMessage,
  inboxMessage,
  neverSaysLive,
  saysLive,
} from '../../support/qa'

/**
 * docs/scenario-queries.md, "Call centre (CC1–CC3)": Sami Al Anazi on /callcentre (from
 * /dev), then the caller's application link from /dev/inbox, in the caller's own window.
 */
const TIMEOUT = LIVE ? 600_000 : 240_000
const HUDA = 'huda.saleh@oasiscoffee.example'
const LAYLA = 'layla.hassan@oasiscoffee.example'

test.describe('Scenario queries: call centre', () => {
  test.beforeEach(() => test.setTimeout(TIMEOUT))

  test(`CC1 Existing CR, existing contact (Inform) ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.open(page, browser, request, 'CC1')
    try {
      await t.row(
        "1 The caller's CR number is 1010000000.",
        [{ cc_cr: '1010000000' }],
        async () => {
          await expect(t.chat.cards('contact_check').last()).toBeVisible()
        },
      )
      await t.row(
        '2 layla.hassan@oasiscoffee.example → Check contact',
        [{ cc_contact_check: LAYLA }],
        async () => {
          const inform = t.chat.cards('inform_tenant').last()
          await expect(inform).toBeVisible()
          await expect(inform.getByRole('button', { name: 'Email sign-in link' })).toBeVisible()
        },
      )
      await t.row('3 Email sign-in link', [{ cc_send_sign_in_link: true }], async () => {
        await expect(
          t.chat
            .cards('inform_tenant')
            .last()
            .getByText(/Sign-in link sent to/),
        ).toBeVisible()
        await expect(t.chat.cards('send_link')).toHaveCount(0)
        const inbox = await t.window()
        await inboxMessage(inbox, { to: LAYLA, template: 'sign_in_link' })
        // No inquiry is created: nothing to Layla but the sign-in link.
        await expectNoInboxMessage(inbox, { to: LAYLA, template: 'complete_application' })
      })
    } finally {
      await t.close()
    }
  })

  test(`CC2 Existing CR, new contact (fresh capture) ${BOTH}`, async ({
    page,
    browser,
    request,
  }) => {
    const t = await Tester.open(page, browser, request, 'CC2')
    try {
      await t.row(
        "1 The caller's CR number is 1010000000. → huda.saleh@oasiscoffee.example → Check contact",
        [{ cc_cr: '1010000000' }, { cc_contact_check: HUDA }],
        async () => {
          await expect(t.chat.cards('inform_tenant')).toHaveCount(0)
          await neverSaysLive(
            t.chat,
            /prefill|already have (her|his|their) details/i,
            'nothing prefilled (M16)',
          )
        },
      )
      await t.row(
        '2–4 Dictate unit and category, basic info, property details',
        [{ cc_capture: 'unit_and_category,basic_info,property_details' }],
        async () => {
          // No documents are asked of the executive.
          await expect(t.chat.cards('document_upload')).toHaveCount(0)
          await expect(t.chat.cards('send_link').last()).toBeVisible()
        },
      )
      await t.row('5 Send application link', [{ cc_submit: true }], async () => {
        await inboxMessage(await t.window(), { to: HUDA, template: 'complete_application' })
      })
      await t.row('6 Open the link → 1234 → terms → upload → Submit', [], async () => {
        await t.openApplicationLinkFromInbox(HUDA)
      })
      await t.row('6 Code, terms, documents', [{ enter_code: '1234' }, ...B.terms, ...B.upload])
      let reference = ''
      await t.row('6 Submit', B.submit, async () => {
        reference = await t.chat.successReference()
      })
      expect(reference).toMatch(/^GEO-/)
      await inboxMessage(await t.window(), { to: HUDA, template: 'submission_email' })
    } finally {
      await t.close()
    }
  })

  test(`CC3 New CR through to submit ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.open(page, browser, request, 'CC3')
    try {
      await t.row(
        "1 The caller's CR number is 1010123456.",
        [{ cc_cr: '1010123456' }],
        async () => {
          // A new CR: no contact check.
          await expect(t.chat.cards('contact_check')).toHaveCount(0)
        },
      )
      await t.row(
        '2–4 Dictate the three sections',
        [{ cc_capture: 'unit_and_category,basic_info,property_details' }],
        async () => {
          await expect(t.chat.cards('document_upload')).toHaveCount(0)
        },
      )
      await t.row('5 Send application link', [{ cc_submit: true }], async () => {
        await inboxMessage(await t.window(), { to: SARA.email, template: 'complete_application' })
      })
      await t.row('6 Open the link', [], () => t.openApplicationLinkFromInbox(SARA.email))
      await t.row('6 Basic Info Change? Yes: last name Al-Ali', [
        { edit_field: ['last_name', 'Al-Ali'] },
      ])
      await t.row('6 Code, terms, documents', [{ enter_code: '1234' }, ...B.terms, ...B.upload])
      let reference = ''
      await t.row('6 Submit', B.submit, async () => {
        reference = await t.chat.successReference()
      })
      expect(reference).toMatch(/^GEO-/)
    } finally {
      await t.close()
    }
  })

  // M1: in the call-centre flows the CR certificate is optional on the application link; the
  // executive's CR stays the inquiry's CR, and a certificate that disagrees is flagged.
  test(`CC3 The caller adds a matching CR certificate ${BOTH}`, async ({
    page,
    browser,
    request,
  }) => {
    const t = await Tester.open(page, browser, request, 'CC3')
    try {
      await t.row("1 The caller's CR number is 1010123456.", [{ cc_cr: '1010123456' }])
      await t.row('2–4 Dictate the three sections', [
        { cc_capture: 'unit_and_category,basic_info,property_details' },
      ])
      await t.row('5 Send application link', [{ cc_submit: true }])
      await t.row('6 Open the link', [], () => t.openApplicationLinkFromInbox(SARA.email))
      await t.row('6 Basic Info Change? Yes: last name Al-Ali', [
        { edit_field: ['last_name', 'Al-Ali'] },
      ])
      await t.row('6 Code and terms', [{ enter_code: '1234' }, ...B.terms])
      await t.row('6 CR certificate (optional, same number as the call)', [], async () => {
        await t.chat.upload('CR certificate', 'cr_certificate_new.pdf')
        await neverSaysLive(t.chat, /differ|doesn'?t match/i, 'nothing to flag')
      })
      await t.row('6 Both profiles', B.upload)
      let reference = ''
      await t.row('6 Submit', B.submit, async () => {
        reference = await t.chat.successReference()
      })
      expect(reference).toMatch(/^GEO-/)
    } finally {
      await t.close()
    }
  })

  test(`CC3 A CR certificate that disagrees is flagged, not blocking ${LIVE_ONLY}`, async ({
    page,
    browser,
    request,
  }) => {
    const t = await Tester.open(page, browser, request, 'CC3')
    try {
      await t.row("1 The caller's CR number is 1010123456.", [{ cc_cr: '1010123456' }])
      await t.row('2–4 Dictate the three sections', [
        { cc_capture: 'unit_and_category,basic_info,property_details' },
      ])
      await t.row('5 Send application link', [{ cc_submit: true }])
      await t.row('6 Open the link', [], () => t.openApplicationLinkFromInbox(SARA.email))
      await t.row('6 Code and terms', [{ enter_code: '1234' }, ...B.terms])
      await t.row('6 A CR certificate with another number', [], async () => {
        // A mismatch gets an agent turn of its own (documents_updated): wait for it.
        const doneBefore = await readDoneEventCount(t.page)
        await t.chat.upload('CR certificate', 'cr_certificate_mismatch.pdf')
        await t.chat.waitForTurnDone(doneBefore)
        await saysLive(t.chat, /differ|doesn'?t match|check/i, 'says the CR differs')
        await neverSaysLive(t.chat, /1010333333|1010123456/, 'no CR number in the reply')
      })
      await t.row('6 Both profiles', B.upload)
      let reference = ''
      await t.row('6 Submit still works', B.submit, async () => {
        reference = await t.chat.successReference()
      })
      expect(reference).toMatch(/^GEO-/)
    } finally {
      await t.close()
    }
  })
})
