import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for the FinAlly E2E suite.
 *
 * The app under test is NOT started by Playwright's `webServer` option --
 * it is provided externally, either by `docker-compose.test.yml` (which
 * sets `E2E_BASE_URL=http://app:8000` for the in-network runner) or by a
 * manually-started `finally` container reachable at `E2E_BASE_URL`
 * (defaults to http://localhost:8000 for local runs). See test/README.md
 * for both run paths.
 *
 * Retries are 0: under LLM_MOCK=true every scenario is deterministic, so a
 * retry would only mask a real flake rather than a legitimate transient
 * network hiccup.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Chromium (M127+) auto-upgrades plain-HTTP navigations to HTTPS
        // for any hostname other than "localhost" ("HTTPS-Upgrades"). The
        // compose runner navigates to http://app:8000 (a non-exempt
        // hostname) and the upgrade attempt fails with
        // net::ERR_SSL_PROTOCOL_ERROR against a plain-HTTP server, so the
        // feature is disabled here rather than only working around it for
        // the localhost-only local run path.
        launchOptions: {
          args: ['--disable-features=HttpsUpgrades'],
        },
      },
    },
  ],
});
