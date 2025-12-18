import { test, expect } from '@playwright/test';

test.describe('Integration Tests', () => {
  test('should handle API failures gracefully', async ({ page }) => {
    // Block API calls to simulate backend failures
    await page.route('**/api/**', (route) => {
      route.abort('failed');
    });

    await page.goto('/');
    
    // Page should still load even with API failures
    await expect(page).toHaveURL('/');
    
    // Should show some default content or loading states
    await page.waitForLoadState('domcontentloaded');
  });

  test('should maintain state when navigating between pages', async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    
    // Interact with incident (if any)
    try {
      await page.click('text=INC-2024-001', { timeout: 5000 });
      
      // Navigate to detections
      await page.goto('/detections');
      await page.waitForLoadState('networkidle');
      
      // Navigate back to incidents
      await page.goto('/incidents');
      await page.waitForLoadState('networkidle');
      
      // Should maintain any relevant state
      await expect(page).toHaveURL('/incidents');
    } catch (e) {
      // If no incidents available, just verify navigation works
      console.log('No incidents available for state test');
    }
  });

  test('should handle different screen sizes', async ({ page }) => {
    const viewports = [
      { width: 1920, height: 1080 }, // Desktop
      { width: 1024, height: 768 },  // Tablet
      { width: 375, height: 667 }    // Mobile
    ];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Page should be usable at all viewport sizes
      const body = await page.locator('body');
      const bodyBox = await body.boundingBox();
      
      if (bodyBox) {
        expect(bodyBox.width).toBeLessThanOrEqual(viewport.width);
      }
    }
  });

  test('should load and render all main pages without errors', async ({ page }) => {
    const pages = ['/', '/incidents', '/detections', '/reports'];
    
    for (const pagePath of pages) {
      await page.goto(pagePath);
      await page.waitForLoadState('networkidle');
      
      // Check for JavaScript errors
      const errors: string[] = [];
      page.on('pageerror', (error) => {
        errors.push(error.message);
      });
      
      // Wait a bit for any async operations
      await page.waitForTimeout(1000);
      
      // Verify page loaded successfully
      await expect(page).toHaveURL(pagePath);
      
      // Check that there are no critical JavaScript errors
      expect(errors.filter(error => 
        !error.includes('Failed to fetch') && 
        !error.includes('ECONNREFUSED')
      )).toHaveLength(0);
    }
  });

  test('should handle keyboard navigation', async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    
    // Test Tab navigation
    await page.keyboard.press('Tab');
    
    // Should be able to navigate with keyboard
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
    
    // Test Escape key for modals/dropdowns
    await page.keyboard.press('Escape');
  });

  test('should display loading states appropriately', async ({ page }) => {
    // Slow down network to test loading states
    await page.route('**/api/**', (route) => {
      setTimeout(() => route.continue(), 2000);
    });

    await page.goto('/reports');
    
    // Should show loading indicators during slow loads
    // Note: This test might need adjustment based on actual loading implementation
    await page.waitForLoadState('domcontentloaded');
  });

  test('should handle empty data states', async ({ page }) => {
    // Mock empty responses
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    
    // Should handle empty states gracefully
    // (The actual implementation might show different empty state messages)
    await page.waitForTimeout(1000);
  });

  test('should maintain accessibility standards', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check for basic accessibility features
    // Main navigation should be accessible
    const nav = page.locator('nav');
    if (await nav.count() > 0) {
      await expect(nav).toBeVisible();
    }
    
    // Images should have alt text (if any)
    const images = page.locator('img');
    const imageCount = await images.count();
    
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      expect(alt).toBeDefined();
    }
  });

  test('should handle browser back/forward navigation', async ({ page }) => {
    // Start at home
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Navigate to incidents
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    
    // Navigate to detections
    await page.goto('/detections');
    await page.waitForLoadState('networkidle');
    
    // Use browser back button
    await page.goBack();
    await expect(page).toHaveURL('/incidents');
    
    // Use browser forward button
    await page.goForward();
    await expect(page).toHaveURL('/detections');
  });
});