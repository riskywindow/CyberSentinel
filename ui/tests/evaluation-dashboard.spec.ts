import { test, expect } from '@playwright/test';

test.describe('Evaluation Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/reports');
    await page.waitForLoadState('networkidle');
  });

  test('should display overall metrics cards', async ({ page }) => {
    // Check main metric cards
    await expect(page.locator('text=Overall Grade')).toBeVisible();
    await expect(page.locator('text=Mean Time to Detection')).toBeVisible();
    await expect(page.locator('text=False Positive Rate')).toBeVisible();
    await expect(page.locator('text=Coverage Score')).toBeVisible();
    
    // Check for grade value
    await expect(page.locator('.text-green-400:has-text("A")')).toBeVisible();
  });

  test('should show demo performance metrics when flag is enabled', async ({ page }) => {
    // Check for Performance Metrics section (only visible when DEMO_FLAGS.mockEvalNumbers is true)
    await expect(page.locator('text=Performance Metrics')).toBeVisible();
    
    // Check for p50 latency
    await expect(page.locator('text=p50 latency')).toBeVisible();
    await expect(page.locator('text=7.2s')).toBeVisible();
    
    // Check for p95 latency
    await expect(page.locator('text=p95 latency')).toBeVisible();
    await expect(page.locator('text=12.8s')).toBeVisible();
    
    // Check for TPR (True Positive Rate)
    await expect(page.locator('text=TPR')).toBeVisible();
    await expect(page.locator('.text-green-400:has-text("87%")')).toBeVisible();
    
    // Check for FPR (False Positive Rate)
    await expect(page.locator('text=FPR')).toBeVisible();
    await expect(page.locator('.text-yellow-400:has-text("0.90%")')).toBeVisible();
    
    // Check for Coverage
    await expect(page.locator('text=Coverage')).toBeVisible();
    await expect(page.locator('.text-blue-400:has-text("82%")')).toBeVisible();
  });

  test('should display detection accuracy trend chart', async ({ page }) => {
    // Check for chart container
    await expect(page.locator('text=Detection Accuracy Trend')).toBeVisible();
    
    // Check for time range selector
    await expect(page.locator('select:has-option("Last 7 Days")')).toBeVisible();
    
    // Check that chart SVG is rendered
    await expect(page.locator('svg')).toBeVisible();
  });

  test('should display response time chart', async ({ page }) => {
    await expect(page.locator('text=Response Time by Scenario')).toBeVisible();
    
    // Check for chart data - should show scenarios like "Lateral Movement"
    await expect(page.locator('text=Lateral Movement')).toBeVisible();
    await expect(page.locator('text=Credential Theft')).toBeVisible();
    await expect(page.locator('text=Data Exfiltration')).toBeVisible();
  });

  test('should show ATT&CK coverage pie chart', async ({ page }) => {
    await expect(page.locator('text=ATT&CK Coverage')).toBeVisible();
    
    // Check for coverage categories
    await expect(page.locator('text=Covered')).toBeVisible();
    await expect(page.locator('text=Partial')).toBeVisible();
    await expect(page.locator('text=Not Covered')).toBeVisible();
    
    // Check for percentage values
    await expect(page.locator('text=88%')).toBeVisible();
    await expect(page.locator('text=8%')).toBeVisible();
    await expect(page.locator('text=4%')).toBeVisible();
  });

  test('should display technique performance table', async ({ page }) => {
    await expect(page.locator('text=Top Technique Performance')).toBeVisible();
    
    // Check for technique entries
    await expect(page.locator('text=T1021.004')).toBeVisible();
    await expect(page.locator('text=SSH')).toBeVisible();
    await expect(page.locator('text=T1059.001')).toBeVisible();
    await expect(page.locator('text=PowerShell')).toBeVisible();
    
    // Check for performance metrics columns
    await expect(page.locator('text=Accuracy')).toBeVisible();
    await expect(page.locator('text=Detections')).toBeVisible();
    await expect(page.locator('text=False Pos.')).toBeVisible();
    
    // Check for percentage values
    await expect(page.locator('text=96%')).toBeVisible(); // SSH accuracy
    await expect(page.locator('text=89%')).toBeVisible(); // PowerShell accuracy
  });

  test('should allow time range selection', async ({ page }) => {
    const timeRangeSelect = page.locator('select:has-option("Last 7 Days")');
    
    // Check default selection
    await expect(timeRangeSelect).toHaveValue('7d');
    
    // Change to 24 hours
    await timeRangeSelect.selectOption('24h');
    await expect(timeRangeSelect).toHaveValue('24h');
    
    // Change to 30 days
    await timeRangeSelect.selectOption('30d');
    await expect(timeRangeSelect).toHaveValue('30d');
  });

  test('should show color-coded performance indicators', async ({ page }) => {
    // Check for green indicators (good performance)
    await expect(page.locator('.text-green-400')).toHaveCount.greaterThan(1);
    
    // Check for trend indicators
    await expect(page.locator('text=-12% from last week')).toBeVisible();
    await expect(page.locator('text=-0.3% from last week')).toBeVisible();
  });

  test('should display charts with proper styling', async ({ page }) => {
    // Check that charts are rendered (SVG elements should be present)
    const svgElements = page.locator('svg');
    await expect(svgElements).toHaveCount.greaterThan(2); // At least area chart, bar chart, and pie chart
    
    // Check for chart containers with proper background
    await expect(page.locator('.bg-slate-800.rounded-lg')).toHaveCount.greaterThan(5);
  });

  test('should be responsive on smaller screens', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    
    // Charts should still be visible and responsive
    await expect(page.locator('text=Detection Accuracy Trend')).toBeVisible();
    await expect(page.locator('text=ATT&CK Coverage')).toBeVisible();
    
    // Check that grid layout adapts (should stack on mobile)
    const gridContainers = page.locator('.grid.grid-cols-1');
    await expect(gridContainers).toHaveCount.greaterThan(0);
  });
});