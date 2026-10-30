import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from '@playwright/test'

type Row = { title: string; project: string; status: string; flaky: boolean }

export default class LiveSummaryReporter implements Reporter {
  private rows: Row[] = []

  onBegin(_config: FullConfig, _suite: Suite): void {
    this.rows = []
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    if (!process.env.E2E_LIVE) return
    if (!test.title.includes('@live')) return
    const flaky = test.title.includes('@flaky')
    this.rows.push({
      title: test.title,
      project: test.parent.project()?.name ?? 'unknown',
      status: result.status,
      flaky,
    })
  }

  onEnd(result: FullResult): void {
    if (!process.env.E2E_LIVE || this.rows.length === 0) return
    const byProject = new Map<string, Row[]>()
    for (const row of this.rows) {
      const list = byProject.get(row.project) ?? []
      list.push(row)
      byProject.set(row.project, list)
    }
    const lines: string[] = ['', '=== E2E-LIVE summary (@flaky excluded from pass rate) ===']
    for (const [project, rows] of byProject) {
      const stable = rows.filter((r) => !r.flaky)
      const flakyRows = rows.filter((r) => r.flaky)
      const passed = stable.filter((r) => r.status === 'passed').length
      const total = stable.length
      const rate = total ? Math.round((100 * passed) / total) : 100
      lines.push(`${project}: ${passed}/${total} stable (${rate}%, gate floor 90%)`)
      for (const f of flakyRows) {
        lines.push(`  @flaky ${f.title}: ${f.status}`)
      }
    }
    lines.push(`Playwright overall: ${result.status}`)
    console.log(lines.join('\n'))
  }
}
