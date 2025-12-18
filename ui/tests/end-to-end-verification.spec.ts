import { test, expect } from '@playwright/test'

test.describe('End-to-End System Verification', () => {
  test('should verify real generated Sigma rules are displayed', async ({ page }) => {
    await page.goto('/detections')
    
    // Wait for the page to load and API data to be fetched
    await page.waitForTimeout(2000)
    
    // Check that we have rules displayed
    const rulesTable = page.locator('table')
    await expect(rulesTable).toBeVisible()
    
    // Look for the specific generated rule title from API
    const generatedRuleTitle = page.locator('text=Detect Ssh Key Lateral Movement To Privileged Host')
    await expect(generatedRuleTitle).toBeVisible()
    
    // Verify rule metadata shows it's AI generated
    const generatedLabel = page.locator('text=AI Generated')
    await expect(generatedLabel).toBeVisible()
    
    // Check that the rule has proper status
    const activeStatus = page.locator('text=Active')
    await expect(activeStatus).toBeVisible()
  })

  test('should verify live evaluation metrics are displayed', async ({ page }) => {
    await page.goto('/evaluation')
    
    // Wait for API data to load
    await page.waitForTimeout(2000)
    
    // Check that overall grade is displayed
    const overallGrade = page.locator('text=Overall Grade').locator('..').locator('.text-3xl')
    await expect(overallGrade).toBeVisible()
    
    // Verify we have mean time to detection
    const mttd = page.locator('text=Mean Time to Detection').locator('..').locator('.text-3xl')
    await expect(mttd).toBeVisible()
    
    // Check false positive rate
    const fpr = page.locator('text=False Positive Rate').locator('..').locator('.text-3xl')
    await expect(fpr).toBeVisible()
    
    // Verify coverage score
    const coverage = page.locator('text=Coverage Score').locator('..').locator('.text-3xl')
    await expect(coverage).toBeVisible()
    
    // Check for demo performance metrics section (should be visible with live data)
    const perfMetrics = page.locator('text=Performance Metrics')
    await expect(perfMetrics).toBeVisible()
  })

  test('should verify API endpoints are serving live data', async ({ page }) => {
    // Test detections API
    const detectionsResponse = await page.request.get('/api/detections/list')
    expect(detectionsResponse.ok()).toBeTruthy()
    const detectionsData = await detectionsResponse.json()
    expect(detectionsData.rules).toBeDefined()
    expect(detectionsData.rules.length).toBeGreaterThan(0)
    
    // Verify the generated rule is in the response
    const hasGeneratedRule = detectionsData.rules.some((rule: any) => 
      rule.title === 'Detect Ssh Key Lateral Movement To Privileged Host'
    )
    expect(hasGeneratedRule).toBeTruthy()
    
    // Test scorecard API
    const scorecardResponse = await page.request.get('/api/reports/scorecard')
    expect(scorecardResponse.ok()).toBeTruthy()
    const scorecardData = await scorecardResponse.json()
    expect(scorecardData.scenarios).toBeDefined()
    expect(scorecardData.scenarios.length).toBeGreaterThan(0)
    
    // Verify metrics structure
    const scenario = scorecardData.scenarios[0]
    expect(scenario.metrics.tpr).toBeDefined()
    expect(scenario.metrics.fpr).toBeDefined()
    expect(scenario.metrics.latency_p50_seconds).toBeDefined()
    expect(scenario.metrics.latency_p95_seconds).toBeDefined()
    expect(scenario.metrics.coverage_score).toBeDefined()
  })

  test('should verify UI displays live data from APIs', async ({ page }) => {
    // First get the live data from APIs
    const scorecardResponse = await page.request.get('/api/reports/scorecard')
    const scorecardData = await scorecardResponse.json()
    const liveMetrics = scorecardData.scenarios[0].metrics
    
    // Now visit the evaluation page and verify the UI shows this data
    await page.goto('/evaluation')
    await page.waitForTimeout(3000) // Give SWR time to fetch and update
    
    // Check that the latency values match what we expect from the API
    const latencyText = `${liveMetrics.latency_p50_seconds}s`
    const latencyElement = page.locator(`text=${latencyText}`)
    await expect(latencyElement).toBeVisible()
    
    // Check TPR percentage
    const tprPercent = `${(liveMetrics.tpr * 100).toFixed(0)}%`
    const tprElement = page.locator('.text-green-400').filter({ hasText: tprPercent })
    await expect(tprElement).toBeVisible()
    
    // Check FPR percentage  
    const fprPercent = `${(liveMetrics.fpr * 100).toFixed(2)}%`
    const fprElement = page.locator('.text-yellow-400').filter({ hasText: fprPercent })
    await expect(fprElement).toBeVisible()
  })

  test('should verify end-to-end workflow: replay generates data → APIs serve it → UI displays it', async ({ page }) => {
    // This test verifies the complete flow works as intended
    
    // 1. Check that we have generated Sigma rules in the file system
    const detectionsResponse = await page.request.get('/api/detections/list')
    const detectionsData = await detectionsResponse.json()
    expect(detectionsData.rules.length).toBeGreaterThan(0)
    
    // 2. Check that we have evaluation metrics
    const scorecardResponse = await page.request.get('/api/reports/scorecard')
    const scorecardData = await scorecardResponse.json()
    expect(scorecardData.scenarios.length).toBeGreaterThan(0)
    
    // 3. Verify the detections page shows the real data
    await page.goto('/detections')
    await page.waitForTimeout(2000)
    
    const realRuleTitle = detectionsData.rules[0].title
    await expect(page.locator(`text=${realRuleTitle}`)).toBeVisible()
    
    // 4. Verify the evaluation page shows the real metrics
    await page.goto('/evaluation')  
    await page.waitForTimeout(3000)
    
    const realLatency = scorecardData.scenarios[0].metrics.latency_p50_seconds
    await expect(page.locator(`text=${realLatency}s`)).toBeVisible()
    
    // 5. Verify this is not just mock data by checking for specific live values
    expect(realLatency).toBeGreaterThan(10) // Our live data should be > 10s
    expect(realLatency).toBeLessThan(15)    // But < 15s based on our generation
  })
})