import { test, expect } from '@playwright/test';

test('settings alpha persists and shows toast', async ({ page }) => {
  await page.goto('/settings');

  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

  await page.getByText('0.10 (More Lenient)').click();
  await expect(page.getByRole('alert')).toHaveText('Settings saved successfully');

  await page.reload();
  const option = page.locator('input[type="radio"][name="alpha"][value="0.1"]');
  await expect(option).toBeChecked();
});
