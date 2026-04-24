// Operator-visible outcome: Triage and Console inline dropdowns are gone. A circular "?" button in the header opens a single "User Guide" page containing both "Console" and "Triage" sections. "← Back" returns to whichever tab launched the guide. Nav-bar tabs are intact.
import { test, expect } from '@playwright/test'

test.describe('User guide — header "?" opens a combined guide page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('inline dropdowns are gone from Console and Triage tabs', async ({ page }) => {
    await page.locator('.header-nav-tab[data-tab="discovery"]').click()
    await expect(page.locator('#discoveryTabContent .user-guide')).toHaveCount(0)
    await expect(page.locator('#discoveryTabContent').getByText('User Guide: Console')).toHaveCount(0)

    await page.locator('.header-nav-tab[data-tab="triage"]').click()
    await expect(page.locator('#triageTabContent .user-guide')).toHaveCount(0)
    await expect(page.locator('#triageTabContent').getByText('User Guide: Triage')).toHaveCount(0)
  })

  test('"?" button renders in the header — circular, transparent, cyan', async ({ page }) => {
    const helpBtn = page.locator('#consoleGuideBtn')
    await expect(helpBtn).toBeVisible()
    await expect(helpBtn).toHaveText('?')

    await expect(page.locator('.header-right #consoleGuideBtn')).toHaveCount(1)

    const box = await helpBtn.boundingBox()
    if (!box) throw new Error('help button has no bounding box')
    expect(Math.abs(Math.round(box.width) - Math.round(box.height))).toBeLessThanOrEqual(2)

    const borderRadius = await helpBtn.evaluate(el => getComputedStyle(el as HTMLElement).borderRadius)
    expect(borderRadius).toMatch(/50%|9999px|\d+px/)
    const bg = await helpBtn.evaluate(el => getComputedStyle(el as HTMLElement).backgroundColor)
    expect(['rgba(0, 0, 0, 0)', 'transparent']).toContain(bg)
  })

  test('clicking "?" opens the combined guide page with Console and Triage sections', async ({ page }) => {
    await page.locator('.header-nav-tab[data-tab="discovery"]').click()
    await page.locator('#consoleGuideBtn').click()

    await expect(page.locator('#userGuideTabContent')).toHaveClass(/active/)
    await expect(page.locator('#discoveryTabContent')).not.toHaveClass(/active/)

    await expect(page.locator('.user-guide-page-title')).toHaveText('User Guide')

    // Console section
    await expect(page.locator('#userGuideTabContent h3', { hasText: 'Console' })).toBeVisible()
    await expect(page.locator('#userGuideTabContent h4', { hasText: 'What This Tab Does' }).first()).toBeVisible()
    await expect(page.locator('#userGuideTabContent h4', { hasText: 'Lifecycle Metrics' })).toBeVisible()

    // Triage section
    await expect(page.locator('#userGuideTabContent h3', { hasText: 'Triage' })).toBeVisible()
    await expect(page.locator('#userGuideTabContent h4', { hasText: 'The Three Workqueues' })).toBeVisible()
    await expect(page.locator('#userGuideTabContent h4', { hasText: 'Available Actions' })).toBeVisible()

    const activeNavTabs = page.locator('.header-nav-tab.active')
    await expect(activeNavTabs).toHaveCount(0)
  })

  test('"← Back" from Console returns to Console tab', async ({ page }) => {
    await page.locator('.header-nav-tab[data-tab="discovery"]').click()
    await page.locator('#consoleGuideBtn').click()
    await expect(page.locator('#userGuideTabContent')).toHaveClass(/active/)

    await page.locator('.guide-back').click()
    await expect(page.locator('#discoveryTabContent')).toHaveClass(/active/)
    await expect(page.locator('#userGuideTabContent')).not.toHaveClass(/active/)
  })

  test('"← Back" from Triage returns to Triage tab', async ({ page }) => {
    await page.locator('.header-nav-tab[data-tab="triage"]').click()
    await page.locator('#consoleGuideBtn').click()
    await expect(page.locator('#userGuideTabContent')).toHaveClass(/active/)

    await page.locator('.guide-back').click()
    await expect(page.locator('#triageTabContent')).toHaveClass(/active/)
    await expect(page.locator('#userGuideTabContent')).not.toHaveClass(/active/)
  })

  test('clicking a nav tab from the guide page restores that tab', async ({ page }) => {
    await page.locator('#consoleGuideBtn').click()
    await expect(page.locator('#userGuideTabContent')).toHaveClass(/active/)

    await page.locator('.header-nav-tab[data-tab="discovery"]').click()
    await expect(page.locator('#discoveryTabContent')).toHaveClass(/active/)
    await expect(page.locator('#userGuideTabContent')).not.toHaveClass(/active/)
  })

  test('nav-bar tabs are intact', async ({ page }) => {
    await expect(page.locator('.header-nav-tab[data-tab="topology"]')).toHaveText('Discovery')
    await expect(page.locator('.header-nav-tab[data-tab="discovery"]')).toHaveText('Console')
    await expect(page.locator('.header-nav-tab[data-tab="triage"]')).toHaveText('Triage')
    await expect(page.locator('.header-nav-tab[data-tab="policy"]')).toHaveText('Policy')
  })
})
