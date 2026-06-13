// Operator-visible outcome: the Discovery hub hexagon is labelled with the run's
// entity_id business name (e.g. "VertexEdge-cb61"), never the tenant_id UUID. The
// tenant_id (a UUID, machine-only per identity rule I2) must not appear anywhere
// on screen — not as the hub label, not in any node's Metadata panel.
import { test, expect, Page } from '@playwright/test'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// Ground truth from the live AOD API (read-only GET — allowed by acceptance rules).
async function groundTruthRun(page: Page) {
  const res = await page.request.get('http://localhost:8001/api/runs')
  expect(res.ok()).toBeTruthy()
  const runs = await res.json()
  expect(runs.length).toBeGreaterThan(0)
  return runs.find((r: any) => String(r.status).startsWith('completed')) || runs[0]
}

async function hubLabel(page: Page): Promise<string> {
  return page.evaluate(() => {
    const d = (window as any).__discovery
    if (!d?.network) throw new Error('Discovery network not exposed')
    return d.network.body.data.nodes.get('aod').label as string
  })
}

test.describe('Discovery — hub identity label (I2)', () => {
  test('hub shows entity_id business name, never the tenant_id UUID', async ({ page }, testInfo) => {
    const run = await groundTruthRun(page)
    expect(run.entity_id, 'API must return entity_id').toBeTruthy()

    await page.goto(`/static/overview/index.html?tenant_id=${encodeURIComponent(run.tenant_id)}`, {
      waitUntil: 'domcontentloaded',
    })
    await page.waitForFunction(() => {
      const d = (window as any).__discovery
      return !!(d && d.network)
    }, { timeout: 20_000 })

    const label = await hubLabel(page)
    console.log(`[hub-label] got="${label}" expected entity_id="${run.entity_id}" tenant_id="${run.tenant_id}"`)
    await page.screenshot({ path: 'test-results/discovery-hub-label.png', fullPage: false })

    // Positive: hub label equals the ground-truth entity_id.
    expect(label).toBe(run.entity_id)
    // Negative: the tenant_id UUID is never the label, and label is not UUID-shaped.
    expect(label).not.toBe(run.tenant_id)
    expect(label).not.toMatch(UUID_RE)
  })

  test('no node Metadata panel exposes the tenant_id UUID', async ({ page }) => {
    const run = await groundTruthRun(page)
    await page.goto(`/static/overview/index.html?tenant_id=${encodeURIComponent(run.tenant_id)}`, {
      waitUntil: 'domcontentloaded',
    })
    await page.waitForFunction(() => !!(window as any).__discovery?.network, { timeout: 20_000 })

    // Every node's metadata must be UUID-free (tenant_id is machine-only, I2).
    const hasUuid = await page.evaluate((tid) => {
      const d = (window as any).__discovery
      const nodes = d.network.body.data.nodes.get()
      return nodes.some((n: any) =>
        Object.values(n.metadata || {}).some((v) => String(v).includes(tid)))
    }, run.tenant_id)
    expect(hasUuid, 'tenant_id UUID must not appear in any node metadata').toBe(false)
  })
})
