import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'

async function captureScreen(page: import('@playwright/test').Page, name: string, fullPage = false) {
  const directory = process.env.PROJECTBRIDGE_SCREENSHOT_DIR
  if (!directory) return
  await mkdir(directory, { recursive: true })
  await page.screenshot({ path: join(directory, `${name}.png`), fullPage, animations: 'disabled' })
}

test('the fixture project can be created, staffed, planned, and refreshed', async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(`${message.text()} [${message.location().url}]`)
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Good ideas need/ })).toBeVisible()
  await expect(page.getByText('Your new project will appear here.')).toBeVisible()
  await page.getByRole('button', { name: 'Start a project' }).click()
  await page.getByRole('button', { name: 'Use CS Club example' }).click()
  await page.getByRole('button', { name: 'Create and review needs' }).click()

  await expect(page.getByRole('heading', { name: 'Make the needs explicit.' })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.evaluate(() => window.scrollTo(0, 0))
  await captureScreen(page, 'mobile-requirements', true)
  await page.getByRole('button', { name: 'Confirm reviewed requirements' }).click()
  await expect(page.getByRole('heading', { name: 'Choose your mix.' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.evaluate(() => window.scrollTo(0, 0))
  await captureScreen(page, 'mobile-team-builder', true)

  const alice = page.locator('article.candidate').filter({ hasText: 'Alice' })
  await expect(alice).toBeVisible()
  await alice.getByRole('button', { name: 'Why this fit?' }).click()
  await expect(alice.getByRole('status')).toBeVisible()
  await expect(page.locator('main > .notice')).toHaveCount(0)
  await captureScreen(page, 'mobile-candidate-explanation', true)
  await alice.getByRole('button', { name: 'Hide explanation' }).click()
  await expect(alice.getByRole('status')).toHaveCount(0)
  await alice.getByRole('button', { name: 'Add' }).click()
  await page.getByRole('button', { name: 'Save my team' }).click()
  await expect(page.getByText('Team saved. You can draft the first roadmap.')).toBeVisible()
  await page.route('**/api/v1/projects/*/roadmap', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 300))
    await route.continue()
  })
  await page.getByRole('button', { name: /Open roadmap/ }).click()
  await expect(page.getByRole('status')).toContainText('Opening your project')
  await expect(page.getByRole('status')).toHaveCount(0)
  await page.unroute('**/api/v1/projects/*/roadmap')
  await expect(page.getByText('NO SAVED PLAN YET')).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.getByRole('button', { name: 'Generate editable draft' }).click()
  await expect(page.getByText('EDITABLE DRAFT · NOT SAVED')).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Save roadmap' }).click()
  await expect(page.getByText(/SAVED PLAN · REVISION/)).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.evaluate(() => window.scrollTo(0, 0))
  await captureScreen(page, 'mobile-saved-roadmap', true)

  const taskStatus = page.locator('select[aria-label$=" status"]').first()
  await expect(taskStatus).toBeVisible()
  await taskStatus.selectOption('done')
  await expect(taskStatus).toHaveValue('done')
  await page.reload()
  await expect(page.getByText(/SAVED PLAN · REVISION/)).toBeVisible()
  await expect(page.locator('select[aria-label$=" status"]').first()).toHaveValue('done')
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('the landing and project form fit a narrow viewport and respond to keyboard activation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Good ideas need/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start a project' })).toBeEnabled()
  await expect(page.getByText(/Connecting to the local demo/)).toHaveCount(0)
  await captureScreen(page, 'desktop-home')
  await page.setViewportSize({ width: 390, height: 844 })
  await captureScreen(page, 'mobile-home')
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.keyboard.press('Tab')
  await expect(page.locator('.nav .brand')).toBeFocused()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  const startButton = page.getByRole('button', { name: 'Start a project' })
  await expect(startButton).toBeFocused()
  await expect.poll(() => startButton.evaluate((button) => getComputedStyle(button).outlineStyle !== 'none')).toBe(true)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Start with the idea.' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  const exampleButton = page.getByRole('button', { name: 'Use CS Club example' })
  for (let tab = 0; tab < 12; tab += 1) {
    if (await exampleButton.evaluate((button) => button === document.activeElement)) break
    await page.keyboard.press('Tab')
  }
  await expect(exampleButton).toBeFocused()
  await page.keyboard.press('Enter')
  await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('button', { name: 'Create and review needs' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Make the needs explicit.' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('an API failure is announced and the demo recovers after retry', async ({ page }) => {
  await page.route('**/api/v1/profiles', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: { code: 'TEST_UNAVAILABLE', message: 'Profiles are temporarily unavailable.' } }),
  }))
  await page.goto('/')
  const alert = page.getByRole('alert')
  await expect(alert).toContainText('Profiles are temporarily unavailable.')
  await captureScreen(page, 'api-error')

  await page.unroute('**/api/v1/profiles')
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { name: /Good ideas need/ })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})
