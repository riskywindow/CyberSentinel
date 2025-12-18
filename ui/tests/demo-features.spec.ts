import { test, expect } from '@playwright/test';

test.describe('CyberSentinel Demo Features', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the home page
    await page.goto('/');
  });

  test('should display home page correctly', async ({ page }) => {
    // Check that the page loads
    await expect(page).toHaveTitle(/CyberSentinel/);
  });

  test('incidents page - action plan approval banner', async ({ page }) => {
    await page.goto('/incidents');
    
    // Wait for incidents to load
    await page.waitForLoadState('networkidle');
    
    // Click on the first incident to view details
    await page.click('text=INC-2024-001', { timeout: 10000 });
    
    // Check for Action Plan section
    await expect(page.locator('text=Action Plan')).toBeVisible();
    
    // Check for approval banner (should be visible due to DEMO_FLAGS.forceHighRiskApprovalBanner)
    await expect(page.locator('text=Requires Approval')).toBeVisible();
    await expect(page.locator('text=High risk playbook. Approval is required before execution.')).toBeVisible();
    
    // Check for dry-run and revert hints
    await expect(page.locator('text=Dry-run ready')).toBeVisible();
    await expect(page.locator('text=Revert supported')).toBeVisible();
  });

  test('incidents page - timeline items are clickable', async ({ page }) => {
    await page.goto('/incidents');
    
    // Wait for incidents to load and click on incident
    await page.waitForLoadState('networkidle');
    await page.click('text=INC-2024-001', { timeout: 10000 });
    
    // Check Timeline section exists
    await expect(page.locator('text=Timeline')).toBeVisible();
    
    // Check for timeline items with hover effect class
    const timelineItems = page.locator('.cursor-pointer.hover\\:bg-slate-700\\/50');
    await expect(timelineItems.first()).toBeVisible();
  });

  test('detections page - showcase rule is visible', async ({ page }) => {
    await page.goto('/detections');
    
    // Wait for rules to load
    await page.waitForLoadState('networkidle');
    
    // Check for the showcase rule
    await expect(page.locator('text=SSH key lateral movement to privileged host')).toBeVisible();
    
    // Check for the required tags (more specific selectors)
    await expect(page.locator('span.bg-slate-600:has-text("ssh")')).toBeVisible();
    await expect(page.locator('span.bg-slate-600:has-text("lateral-movement")')).toBeVisible();
    await expect(page.locator('span.bg-slate-600:has-text("T1021.004")')).toBeVisible();
  });

  test('detections page - rule editor prefilled', async ({ page }) => {
    await page.goto('/detections');
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Click "Create New Rule" or similar button
    await page.click('text=Create Rule', { timeout: 10000 });
    
    // Check that the rule editor opens with prefilled content
    await expect(page.locator('input[value*="SSH key lateral movement"]')).toBeVisible();
    await expect(page.locator('textarea[value*="Detects unusual SSH key authentication patterns"]')).toBeVisible();
  });

  test('reports page - evaluation metrics', async ({ page }) => {
    await page.goto('/reports');
    
    // Wait for reports to load
    await page.waitForLoadState('networkidle');
    
    // Check for Performance Metrics section (only visible when DEMO_FLAGS.mockEvalNumbers is true)
    await expect(page.locator('text=Performance Metrics')).toBeVisible();
    
    // Check for specific metrics
    await expect(page.locator('text=p50 latency')).toBeVisible();
    await expect(page.locator('text=7.2s')).toBeVisible();
    
    await expect(page.locator('text=p95 latency')).toBeVisible();
    await expect(page.locator('text=12.8s')).toBeVisible();
    
    await expect(page.locator('text=TPR')).toBeVisible();
    await expect(page.locator('text=87%')).toBeVisible();
    
    await expect(page.locator('text=FPR')).toBeVisible();
    await expect(page.locator('text=0.90%')).toBeVisible();
    
    await expect(page.locator('text=Coverage')).toBeVisible();
    await expect(page.locator('text=82%')).toBeVisible();
  });

  test('graph page - legend entries', async ({ page }) => {
    await page.goto('/graph');
    
    // Wait for graph to load
    await page.waitForLoadState('networkidle');
    
    // Check for ATT&CK Technique entry in legend
    await expect(page.locator('text=ATT&CK Technique')).toBeVisible();
    
    // Check for Lateral Movement entry in legend (more specific)
    await expect(page.locator('.text-slate-300:has-text("Lateral Movement")')).toBeVisible();
  });

  test('navigation between main sections', async ({ page }) => {
    // Test navigation to each main section
    const sections = [
      { path: '/incidents', text: 'Incidents' },
      { path: '/detections', text: 'Detections' },
      { path: '/reports', text: 'Reports' },
      { path: '/graph', text: 'Attack Graph' }
    ];

    for (const section of sections) {
      await page.goto(section.path);
      await page.waitForLoadState('networkidle');
      
      // Verify we're on the correct page
      await expect(page).toHaveURL(section.path);
    }
  });

  test('responsive design - mobile view', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check that page renders without horizontal scroll
    const body = await page.locator('body');
    const bodyBox = await body.boundingBox();
    expect(bodyBox?.width).toBeLessThanOrEqual(375);
  });
});