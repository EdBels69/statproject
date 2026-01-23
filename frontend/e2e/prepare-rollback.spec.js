import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test('prepare mode can add derived column and rollback', async ({ page }) => {
  const csvPath = path.resolve(__dirname, '../../test_upload.csv');

  await page.goto('/upload');
  await page.setInputFiles('#file-upload', csvPath);

  await page.waitForURL(/\/profile\//);

  await page.getByRole('button', { name: 'Подготовка данных' }).click();
  await page.waitForURL(/\/prepare\//);

  await page.getByRole('button', { name: /Новые колонки/i }).click();

  await page.getByPlaceholder('например: delta_score').fill('delta');

  await page.getByText('A', { exact: true }).locator('..').locator('select').selectOption('col1');
  await page.getByText('B', { exact: true }).locator('..').locator('select').selectOption('col1');

  await page.getByRole('button', { name: 'Добавить колонку' }).click();

  const rollbackButton = page.getByRole('button', { name: /Откат/ });
  await expect(rollbackButton).toContainText('(1)');

  page.once('dialog', (dialog) => dialog.accept());
  await rollbackButton.click();

  await expect(rollbackButton).toBeDisabled();
});

