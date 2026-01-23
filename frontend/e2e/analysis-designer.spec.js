import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test('analysis designer loads for a dataset', async ({ page }) => {
  const pageErrors = [];
  const consoleErrors = [];

  page.on('pageerror', (err) => {
    pageErrors.push(err?.message || String(err));
  });
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  const csvPath = path.resolve(__dirname, '../../test_upload.csv');

  await page.goto('/upload');
  await page.setInputFiles('#file-upload', csvPath);

  await page.waitForURL(/\/profile\//);
  const match = page.url().match(/\/profile\/([^/?#]+)/);
  expect(match?.[1]).toBeTruthy();
  const datasetId = match[1];

  await page.goto(`/design/${datasetId}`);

  const ok = page.getByText('Конструктор').first();
  const crash = page.getByRole('heading', { name: 'Something went wrong' });

  const outcome = await Promise.race([
    ok.waitFor({ state: 'visible', timeout: 15000 }).then(() => 'ok').catch(() => null),
    crash.waitFor({ state: 'visible', timeout: 15000 }).then(() => 'crash').catch(() => null),
  ]);

  if (outcome !== 'ok') {
    const summary = page.getByText('View error details');
    if (await summary.count()) {
      await summary.click();
    }

    const details = page.locator('details div').first();
    const detailsText = (await details.count()) ? await details.textContent() : '';
    const combined = [
      detailsText?.trim(),
      pageErrors.length ? `pageerror: ${pageErrors.join(' | ')}` : '',
      consoleErrors.length ? `console: ${consoleErrors.join(' | ')}` : '',
    ].filter(Boolean).join('\n');

    throw new Error(combined || 'Analysis designer crashed');
  }
});
