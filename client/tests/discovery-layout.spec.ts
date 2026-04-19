import { test, expect, Page } from '@playwright/test'

// Operator-visible outcome (per B17 / Playwright Acceptance):
// When Discovery loads, the tenant hex sits well to the left of the seven
// observation-plane triangles (canvas X-gap ≥ 260). The seven planes are
// vertically spaced with a Y-gap ≥ 90 between adjacent planes. A user can
// grab any plane and drag it freely in BOTH axes — both ΔX and ΔY must be
// meaningfully non-zero (>40px) after a diagonal drag.

type Pos = { x: number; y: number }

async function getPositions(page: Page): Promise<Record<string, Pos>> {
  return page.evaluate(() => {
    const d = (window as any).__discovery
    if (!d?.network) throw new Error('Discovery network not exposed')
    return d.network.getPositions() as Record<string, Pos>
  })
}

async function canvasToDOM(page: Page, p: Pos): Promise<Pos> {
  return page.evaluate((pos) => {
    const d = (window as any).__discovery
    const dom = d.network.canvasToDOM(pos)
    const rect = (document.querySelector('canvas') as HTMLElement).getBoundingClientRect()
    return { x: rect.left + dom.x, y: rect.top + dom.y }
  }, p)
}

test.describe('Discovery — layout + interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/static/overview/index.html', { waitUntil: 'domcontentloaded' })
    // Wait for stabilization — loading message clears when ready
    await page.waitForFunction(() => {
      const d = (window as any).__discovery
      return !!(d && d.network)
    }, { timeout: 20_000 })
    // Small settle delay for post-stabilization unfix + moveNode
    await page.waitForTimeout(1200)
  })

  test('hub is far left of observation planes', async ({ page }, testInfo) => {
    const pos = await getPositions(page)
    expect(pos['aod']).toBeDefined()
    const planeIds = ['plane-discovery', 'plane-idp', 'plane-cmdb', 'plane-cloud', 'plane-network', 'plane-finance', 'plane-endpoint']
    const planeXs = planeIds.map(id => pos[id]?.x).filter((x): x is number => x !== undefined)
    expect(planeXs.length).toBe(7)
    const leftmostPlaneX = Math.min(...planeXs)
    const hubX = pos['aod'].x
    const gap = leftmostPlaneX - hubX
    console.log(`[hub-gap] hubX=${hubX.toFixed(0)} leftmostPlaneX=${leftmostPlaneX.toFixed(0)} gap=${gap.toFixed(0)}`)
    await page.screenshot({ path: 'test-results/discovery-initial.png', fullPage: false })
    expect(gap).toBeGreaterThanOrEqual(260)
  })

  test('observation planes have vertical breathing room', async ({ page }) => {
    const pos = await getPositions(page)
    const planeIds = ['plane-discovery', 'plane-idp', 'plane-cmdb', 'plane-cloud', 'plane-network', 'plane-finance', 'plane-endpoint']
    const ys = planeIds.map(id => pos[id].y).sort((a, b) => a - b)
    const gaps = ys.slice(1).map((y, i) => y - ys[i])
    const minGap = Math.min(...gaps)
    console.log(`[plane-y-gaps] ${gaps.map(g => g.toFixed(0)).join(', ')}`)
    expect(minGap).toBeGreaterThanOrEqual(90)
  })

  test('plane node drags freely on both X and Y axes', async ({ page }, testInfo) => {
    const before = await getPositions(page)
    const target = 'plane-cmdb'
    const startCanvas = before[target]
    const startDom = await canvasToDOM(page, startCanvas)

    await page.screenshot({ path: 'test-results/discovery-before-drag.png', fullPage: false })

    // Diagonal drag — DOM pixels (80 right, 80 down)
    await page.mouse.move(startDom.x, startDom.y)
    await page.mouse.down()
    await page.mouse.move(startDom.x + 40, startDom.y + 40, { steps: 5 })
    await page.mouse.move(startDom.x + 80, startDom.y + 80, { steps: 10 })
    await page.mouse.up()
    await page.waitForTimeout(300)

    const after = await getPositions(page)
    const dx = after[target].x - before[target].x
    const dy = after[target].y - before[target].y
    console.log(`[drag] ${target} dx=${dx.toFixed(0)} dy=${dy.toFixed(0)}`)

    await page.screenshot({ path: 'test-results/discovery-after-drag.png', fullPage: false })

    // Both deltas must be meaningful — this is the whole point (rank-axis unlock)
    expect(Math.abs(dx)).toBeGreaterThan(40)
    expect(Math.abs(dy)).toBeGreaterThan(40)
  })
})
