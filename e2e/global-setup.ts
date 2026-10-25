import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const fixturesDir = path.join(__dirname, 'fixtures/files')

const MIN_PDF = Buffer.from(
  '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
  'utf8',
)

export default async function globalSetup() {
  fs.mkdirSync(fixturesDir, { recursive: true })
  fs.writeFileSync(path.join(fixturesDir, 'company_profile.pdf'), MIN_PDF)
  fs.writeFileSync(path.join(fixturesDir, 'brand_profile.pdf'), MIN_PDF)
  fs.writeFileSync(path.join(fixturesDir, 'notes.txt'), Buffer.from('hello\n'))
  const sixMb = Buffer.alloc(6 * 1024 * 1024, 'x')
  fs.writeFileSync(path.join(fixturesDir, 'too_big.pdf'), Buffer.concat([MIN_PDF, sixMb]))
  fs.mkdirSync(path.join(__dirname, 'results'), { recursive: true })
}
