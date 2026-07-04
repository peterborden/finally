import { defineConfig, devices } from '@playwright/test';

/**
 * FinAlly E2E + API contract test configuration.
 *
 * Two projects:
 *   - `api`  : pure HTTP request tests asserting the exact §5 response shapes.
 *              No browser needed. Runs the moment backend+db+llm are merged.
 *   - `e2e`  : browser UI tests driving the §10 terminal UI.
 *
 * BASE_URL selects the target:
 *   - Local (app already running):     BASE_URL=http://localhost:8000
 *   - docker-compose.test.yml network: BASE_URL=http://app:8000  (default in compose)
 *   - Fallback default:                http://localhost:8000
 */
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: '.',
  // Trades mutate shared single-user state (one DB). Run serially so specs
  // don't stomp each other's cash/positions. Determinism > speed here.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'api',
      testDir: './api',
      use: {}, // request-only; no browser context
    },
    {
      name: 'e2e',
      testDir: './e2e',
      dependencies: ['api'], // if the API contract is broken, fail fast before UI
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1600, height: 1000 },
        // The app is served over plain HTTP. Recent Chromium auto-upgrades http->https
        // for non-localhost hosts (e.g. the compose service name `app`), which fails
        // the TLS handshake against the plaintext server (ERR_SSL_PROTOCOL_ERROR).
        // Disable the upgrade so navigations to http://app:8000 work in CI/compose.
        launchOptions: {
          args: ['--disable-features=HttpsUpgrades,HttpsFirstBalancedModeAutoEnable'],
        },
      },
    },
  ],
});
