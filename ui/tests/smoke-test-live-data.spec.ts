import { test, expect } from '@playwright/test'

test.describe('Live Data Smoke Test', () => {
  test('API endpoints serve real generated data', async ({ page }) => {
    // Test that detections API returns our generated rule
    const detectionsResponse = await page.request.get('/api/detections/list')
    expect(detectionsResponse.ok()).toBeTruthy()
    const detectionsData = await detectionsResponse.json()
    
    console.log('Detections API Response:', JSON.stringify(detectionsData, null, 2))
    
    expect(detectionsData.rules).toBeDefined()
    expect(detectionsData.rules.length).toBeGreaterThan(0)
    
    // Check for our generated SSH rule
    const hasSSHRule = detectionsData.rules.some((rule: any) => 
      rule.title.includes('Ssh Key Lateral Movement') || 
      rule.title.includes('SSH')
    )
    expect(hasSSHRule).toBeTruthy()
    
    // Test that scorecard API returns real metrics
    const scorecardResponse = await page.request.get('/api/reports/scorecard')
    expect(scorecardResponse.ok()).toBeTruthy()
    const scorecardData = await scorecardResponse.json()
    
    console.log('Scorecard API Response:', JSON.stringify(scorecardData, null, 2))
    
    expect(scorecardData.scenarios).toBeDefined()
    expect(scorecardData.scenarios.length).toBeGreaterThan(0)
    
    // Verify we have real metrics from the harness run
    const scenario = scorecardData.scenarios[0]
    expect(scenario.scenario).toBe('lateral_move_ssh')
    expect(scenario.metrics.tpr).toBe(1.0)
    expect(scenario.metrics.fpr).toBe(0.0)
    expect(scenario.metrics.latency_p50_seconds).toBeGreaterThan(10)
    expect(scenario.metrics.latency_p95_seconds).toBeGreaterThan(20)
    expect(scenario.metrics.coverage_score).toBe(0.82)
  })

  test('UI loads and displays data from APIs', async ({ page }) => {
    // Test detections page loads
    await page.goto('/detections')
    await page.waitForLoadState('networkidle')
    
    // Should see the rules table
    await expect(page.locator('table')).toBeVisible()
    await expect(page.locator('text=Detection Rules')).toBeVisible()
    
    // Test evaluation page loads  
    await page.goto('/evaluation')
    await page.waitForLoadState('networkidle')
    
    // Should see the metrics cards
    await expect(page.locator('text=Overall Grade')).toBeVisible()
    await expect(page.locator('text=Mean Time to Detection')).toBeVisible()
    await expect(page.locator('text=False Positive Rate')).toBeVisible()
    await expect(page.locator('text=Coverage Score')).toBeVisible()
  })

  test('End-to-end workflow validation', async ({ page }) => {
    // This validates the complete flow:
    // 1. harness.py generates Sigma rules and metrics
    // 2. API endpoints serve this data  
    // 3. UI components fetch and display the data
    
    // Get the live data
    const detectionsResponse = await page.request.get('/api/detections/list')
    const detectionsData = await detectionsResponse.json()
    const scorecardResponse = await page.request.get('/api/reports/scorecard')
    const scorecardData = await scorecardResponse.json()
    
    // Verify we have both types of generated data
    expect(detectionsData.rules.length).toBeGreaterThan(0)
    expect(scorecardData.scenarios.length).toBeGreaterThan(0)
    
    // Verify the data is fresh (not old mocks)
    const latency = scorecardData.scenarios[0].metrics.latency_p50_seconds
    expect(latency).toBeGreaterThan(11) // Our generated data is around 11.2
    expect(latency).toBeLessThan(12)    // Should be close to 11.2
    
    // Navigate to pages and verify they load without errors
    await page.goto('/detections')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[class*="error"]')).toHaveCount(0)
    
    await page.goto('/evaluation')  
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[class*="error"]')).toHaveCount(0)
    
    console.log('✅ End-to-end workflow validated successfully!')
    console.log(`📊 Found ${detectionsData.rules.length} detection rules`)
    console.log(`📈 Latency: ${latency}s, TPR: ${scorecardData.scenarios[0].metrics.tpr}, FPR: ${scorecardData.scenarios[0].metrics.fpr}`)
  })
})