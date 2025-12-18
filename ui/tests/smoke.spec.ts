import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('homepage loads correctly', async ({ page }) => {
    await page.goto('/');
    
    // Just verify the page loads without errors
    await expect(page).toHaveURL('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('incidents page is accessible', async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL('/incidents');
  });

  test('detections page is accessible', async ({ page }) => {
    await page.goto('/detections');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL('/detections');
  });

  test('reports page is accessible', async ({ page }) => {
    await page.goto('/reports');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL('/reports');
  });

  test('can navigate between pages', async ({ page }) => {
    // Start at home
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    // Navigate to each page
    await page.goto('/incidents');
    await expect(page).toHaveURL('/incidents');
    
    await page.goto('/detections');
    await expect(page).toHaveURL('/detections');
    
    await page.goto('/reports');
    await expect(page).toHaveURL('/reports');
  });
});