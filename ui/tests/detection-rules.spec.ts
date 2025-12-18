import { test, expect } from '@playwright/test';

test.describe('Detection Rules', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/detections');
    await page.waitForLoadState('networkidle');
  });

  test('should display showcase rule at top of list', async ({ page }) => {
    // Check that the showcase rule appears first
    const firstRule = page.locator('tbody tr').first();
    await expect(firstRule.locator('text=SSH key lateral movement to privileged host')).toBeVisible();
    
    // Check rule description
    await expect(firstRule.locator('text=Detects unusual SSH key authentication patterns that may indicate lateral movement')).toBeVisible();
    
    // Check AI Generated source
    await expect(firstRule.locator('text=AI Generated')).toBeVisible();
    
    // Check tags are displayed (more specific selectors)
    await expect(firstRule.locator('span.bg-slate-600:has-text("ssh")')).toBeVisible();
    await expect(firstRule.locator('span.bg-slate-600:has-text("lateral-movement")')).toBeVisible();
    await expect(firstRule.locator('span.bg-slate-600:has-text("T1021.004")')).toBeVisible();
  });

  test('should show correct rule metadata', async ({ page }) => {
    const showcaseRule = page.locator('tr:has-text("SSH key lateral movement to privileged host")');
    
    // Check category
    await expect(showcaseRule.locator('text=Lateral Movement')).toBeVisible();
    
    // Check severity indicator
    await expect(showcaseRule.locator('.text-orange-400:has-text("HIGH")')).toBeVisible();
    
    // Check status
    await expect(showcaseRule.locator('.text-green-400:has-text("Active")')).toBeVisible();
    
    // Check performance metrics
    await expect(showcaseRule.locator('text=8')).toBeVisible(); // Detection count
    await expect(showcaseRule.locator('text=1.0%')).toBeVisible(); // False positive rate
  });

  test('should allow rule selection and bulk actions', async ({ page }) => {
    // Select the showcase rule checkbox
    const showcaseRuleRow = page.locator('tr:has-text("SSH key lateral movement to privileged host")');
    await showcaseRuleRow.locator('input[type="checkbox"]').click();
    
    // Check that bulk action buttons appear
    await expect(page.locator('text=1 selected')).toBeVisible();
    await expect(page.locator('button:has-text("Enable")')).toBeVisible();
    await expect(page.locator('button:has-text("Disable")')).toBeVisible();
    await expect(page.locator('button:has-text("Delete")')).toBeVisible();
  });

  test('should filter rules correctly', async ({ page }) => {
    // Test severity filter
    await page.selectOption('select:has-option("high")', 'high');
    
    // Should still show the showcase rule (high severity)
    await expect(page.locator('text=SSH key lateral movement to privileged host')).toBeVisible();
    
    // Test category filter
    await page.selectOption('select:has-option("Lateral Movement")', 'Lateral Movement');
    
    // Should still show the showcase rule (Lateral Movement category)
    await expect(page.locator('text=SSH key lateral movement to privileged host')).toBeVisible();
    
    // Test status filter
    await page.selectOption('select:has-option("active")', 'active');
    
    // Should still show the showcase rule (active status)
    await expect(page.locator('text=SSH key lateral movement to privileged host')).toBeVisible();
  });

  test('should show rule actions', async ({ page }) => {
    const showcaseRule = page.locator('tr:has-text("SSH key lateral movement to privileged host")');
    
    // Check for action buttons
    await expect(showcaseRule.locator('button[title="Edit Rule"]')).toBeVisible();
    await expect(showcaseRule.locator('button[title="Test Rule"]')).toBeVisible();
    await expect(showcaseRule.locator('button[title="View Details"]')).toBeVisible();
    await expect(showcaseRule.locator('button[title="Delete Rule"]')).toBeVisible();
  });

  test('should open rule editor with prefilled content', async ({ page }) => {
    // Look for Create/New Rule button - might be in different locations
    const createButtons = [
      'button:has-text("Create Rule")',
      'button:has-text("New Rule")',
      'button:has-text("Add Rule")',
      'text=Create Rule',
      'text=New Rule'
    ];
    
    let clicked = false;
    for (const selector of createButtons) {
      try {
        await page.click(selector, { timeout: 2000 });
        clicked = true;
        break;
      } catch (e) {
        // Continue to next selector
      }
    }
    
    if (!clicked) {
      // If no create button found, click edit on the showcase rule
      await page.locator('tr:has-text("SSH key lateral movement to privileged host")').locator('button[title="Edit Rule"]').click();
    }
    
    // Check that rule editor opens with demo content when DEMO_FLAGS.seedShowcaseRule is true
    await expect(page.locator('input[value*="SSH key lateral movement"]')).toBeVisible({ timeout: 10000 });
    
    // Check prefilled fields
    await expect(page.locator('textarea:has-text("Detects unusual SSH key authentication patterns")')).toBeVisible();
    
    // Check YAML content is prefilled
    await expect(page.locator('textarea:has-text("ssh.auth.method")')).toBeVisible();
  });

  test('should display rule count correctly', async ({ page }) => {
    // Check that the rule count includes the showcase rule
    const ruleCount = page.locator('text=/Detection Rules \\(\\d+\\)/');
    await expect(ruleCount).toBeVisible();
    
    // Should show at least 5 rules (4 original + 1 showcase)
    await expect(page.locator('tbody tr')).toHaveCount(5);
  });

  test('should show performance indicators', async ({ page }) => {
    const showcaseRule = page.locator('tr:has-text("SSH key lateral movement to privileged host")');
    
    // Check detection count
    await expect(showcaseRule.locator('text=8')).toBeVisible();
    
    // Check false positive rate with good color (green for low FP rate)
    const fpRate = showcaseRule.locator('.text-green-400:has-text("1.0%")');
    await expect(fpRate).toBeVisible();
  });
});