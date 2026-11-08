import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const scenarioDir = path.join(repoRoot, 'frontend/src/mocks/scenarios/parity')

type FeWhen =
  | { type: 'message'; textEquals?: string }
  | { type: 'action'; action: string }

type FeTurn = { when: FeWhen; events: unknown[] }

type FeScenarioFile = {
  name: string
  turns?: FeTurn[]
}

const PARITY_SCENARIOS = [
  'happy-path-cr',
  'skip-cr',
  'existing-cr-sign-in',
  'landline-only',
  'two-malls-named',
  'wrong-otp-three-times',
  's14-out-of-order',
  'rd-cr-question',
  'rd-type-or-upload',
] as const

function loadScenario(name: string): FeScenarioFile {
  const raw = fs.readFileSync(path.join(scenarioDir, `${name}.json`), 'utf8')
  return JSON.parse(raw) as FeScenarioFile
}

async function replayWhen(
  inquiry: FeInquiryPage,
  when: FeWhen,
  otpCodes: string[],
  scenarioName: string,
) {
  if (when.type === 'message') {
    await inquiry.say(when.textEquals ?? '')
    return
  }
  if (when.action === 'confirm_card') {
    await inquiry.confirmCard()
    return
  }
  if (when.action === 'cr_answer') {
    await inquiry.answerCrQuestion(scenarioName === 'rd-cr-question')
    return
  }
  if (when.action === 'verify_email') {
    await inquiry.verifyEmail()
    return
  }
  if (when.action === 'submit_otp') {
    const code = otpCodes.shift() ?? '1234'
    await inquiry.enterCode(code)
    return
  }
  if (when.action === 'documents_updated') {
    return
  }
}

test.describe('Parity golden fixtures @fe', () => {
  for (const name of PARITY_SCENARIOS) {
    test(`replays ${name}`, async ({ page }, testInfo) => {
      test.setTimeout(180_000)
      const scenario = loadScenario(name)
      const inquiry = new FeInquiryPage(page)
      await inquiry.openMock(name)

      const otpCodes =
        name === 'wrong-otp-three-times'
          ? ['0000', '0000', '0000', '1234']
          : name === 's14-out-of-order'
            ? ['1234']
            : ['1234']

      async function uploadRequiredDocs() {
        if (await inquiry.cards('document_upload').isVisible()) {
          await inquiry.upload('Company Profile', 'company_profile.pdf')
          await inquiry.upload('Brand Profile', 'brand_profile.pdf')
        }
      }

      for (const turn of scenario.turns ?? []) {
        await replayWhen(inquiry, turn.when, otpCodes, name)
        if (turn.when.type === 'action' && turn.when.action === 'submit_otp') {
          if (name === 's14-out-of-order') {
            await uploadRequiredDocs()
          } else if (name === 'wrong-otp-three-times' && otpCodes.length === 0) {
            await uploadRequiredDocs()
          } else if (
            name !== 'wrong-otp-three-times' &&
            name !== 's14-out-of-order' &&
            name !== 'rd-type-or-upload'
          ) {
            await uploadRequiredDocs()
          }
        }
        if (
          turn.when.type === 'action' &&
          turn.when.action === 'verify_email' &&
          name === 'landline-only'
        ) {
          await uploadRequiredDocs()
        }
      }

      if (name === 'existing-cr-sign-in' || name === 'rd-cr-question') {
        await expect(inquiry.cards('sign_in_prompt')).toBeVisible()
      } else if (name === 'two-malls-named') {
        const text = (await inquiry.lastBotText()).toLowerCase()
        expect(text).toMatch(/which/)
      } else {
        await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
      }

      await finishA11yOnPage(page, testInfo.project.name)
    })
  }
})
