import { defineConfig } from '@playwright/test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const apiUrl = 'http://127.0.0.1:8019'
const baseURL = 'http://127.0.0.1:5179'
const dbPath = join(tmpdir(), 'projectbridge-e2e.sqlite3').replaceAll('\\', '/')
const processFile = join(tmpdir(), 'projectbridge-e2e-processes.json')

export default defineConfig({
  testDir: './e2e',
  globalTeardown: './e2e/global-teardown.ts',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL,
    browserName: 'chromium',
    channel: 'chrome',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: {
      command: `"${process.execPath}" e2e/server-manager.mjs`,
      cwd: '.',
      url: baseURL,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        APP_ORIGIN: baseURL,
        DATABASE_URL: `sqlite:///${dbPath}`,
        PROJECTBRIDGE_API_ORIGIN: apiUrl,
        PROJECTBRIDGE_E2E_PID_FILE: processFile,
      },
    },
})
