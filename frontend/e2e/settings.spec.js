import { test, expect } from '@playwright/test';

test('settings alpha persists and shows toast', async ({ page }) => {
  await page.goto('/settings');

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  await page.locator('label', { has: page.locator('input[type="radio"][name="alpha"][value="0.1"]') }).click();
  await expect(page.getByRole('alert')).toBeVisible();

  await page.reload();
  const option = page.locator('input[type="radio"][name="alpha"][value="0.1"]');
  await expect(option).toBeChecked();
});
