import { test, expect } from '@playwright/test';

test.describe('Home page', () => {
  test('shows ATLAS heading and Backend: ok status', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'ATLAS' })).toBeVisible();
    await expect(page.getByText('Backend: ok')).toBeVisible({ timeout: 10_000 });
  });
});
