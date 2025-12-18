import { test, expect } from '@playwright/test';

test.describe('Incident Details Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
  });

  test('should show incident overview with correct details', async ({ page }) => {
    // Click on incident INC-2024-001
    await page.click('text=INC-2024-001');
    
    // Verify incident header information
    await expect(page.locator('text=INC-2024-001')).toBeVisible();
    await expect(page.locator('text=Lateral Movement via SSH Key Compromise')).toBeVisible();
    await expect(page.locator('text=Investigating')).toBeVisible();
    
    // Check overview section is expanded by default
    await expect(page.locator('text=Overview')).toBeVisible();
    await expect(page.locator('text=Alice Chen')).toBeVisible();
    
    // Check ATT&CK techniques
    await expect(page.locator('text=T1021.004')).toBeVisible();
    await expect(page.locator('text=T1078.004')).toBeVisible();
    await expect(page.locator('text=T1543.003')).toBeVisible();
  });

  test('should expand and collapse sections', async ({ page }) => {
    await page.click('text=INC-2024-001');
    
    // Timeline should be expanded by default
    await expect(page.locator('text=Suspicious SSH key authentication detected')).toBeVisible();
    
    // Collapse timeline
    await page.click('button:has-text("Timeline")');
    
    // Timeline content should be hidden
    await expect(page.locator('text=Suspicious SSH key authentication detected')).not.toBeVisible();
    
    // Expand entities section
    await page.click('button:has-text("Entities")');
    
    // Entities should be visible
    await expect(page.locator('text=web-01')).toBeVisible();
    await expect(page.locator('text=db-02')).toBeVisible();
    await expect(page.locator('text=app-03')).toBeVisible();
  });

  test('action plan section should show high risk approval', async ({ page }) => {
    await page.click('text=INC-2024-001');
    
    // Action plan should be expanded by default due to expandedSections config
    await expect(page.locator('text=Action Plan')).toBeVisible();
    
    // Check approval banner
    await expect(page.locator('text=Requires Approval')).toBeVisible();
    await expect(page.locator('text=High risk playbook. Approval is required before execution.')).toBeVisible();
    
    // Check playbook details
    await expect(page.locator('text=isolate host')).toBeVisible();
    await expect(page.locator('text=disable ssh')).toBeVisible();
    await expect(page.locator('text=collect forensic evidence')).toBeVisible();
    
    // Check risk tier
    await expect(page.locator('text=HIGH')).toBeVisible();
    
    // Check operational hints
    await expect(page.locator('text=Dry-run ready')).toBeVisible();
    await expect(page.locator('text=Revert supported')).toBeVisible();
  });

  test('timeline items should have hover effects', async ({ page }) => {
    await page.click('text=INC-2024-001');
    
    // Find timeline item with the demo clickable class
    const timelineItem = page.locator('.cursor-pointer.hover\\:bg-slate-700\\/50').first();
    await expect(timelineItem).toBeVisible();
    
    // Verify the timeline item contains expected content
    await expect(page.locator('text=Suspicious SSH key authentication detected')).toBeVisible();
    await expect(page.locator('text=Scout Agent')).toBeVisible();
  });

  test('should display artifacts section', async ({ page }) => {
    await page.click('text=INC-2024-001');
    
    // Expand artifacts section
    await page.click('button:has-text("Artifacts")');
    
    // Check for artifacts
    await expect(page.locator('text=auth.log')).toBeVisible();
    await expect(page.locator('text=ssh_connections.pcap')).toBeVisible();
    await expect(page.locator('text=process_dump.json')).toBeVisible();
    
    // Check download buttons
    await expect(page.locator('button:has-text("Download")')).toHaveCount(3);
  });

  test('should show proper status indicators', async ({ page }) => {
    await page.click('text=INC-2024-001');
    
    // Check severity indicator
    await expect(page.locator('.bg-red-500\\/10')).toBeVisible(); // Critical severity background
    
    // Check status badge
    await expect(page.locator('.bg-yellow-500\\/10')).toBeVisible(); // Investigating status background
    
    // Check timeline event status
    await expect(page.locator('text=executing')).toBeVisible();
  });
});