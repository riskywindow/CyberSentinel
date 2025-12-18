# CyberSentinel UI Testing

This directory contains end-to-end tests for the CyberSentinel UI using Playwright.

## Test Structure

### Test Files

- **`smoke.spec.ts`** - Basic smoke tests to verify core functionality
- **`demo-features.spec.ts`** - Tests for the demo features and feature flags
- **`incident-details.spec.ts`** - Detailed tests for incident management functionality  
- **`detection-rules.spec.ts`** - Tests for detection rules management
- **`evaluation-dashboard.spec.ts`** - Tests for the evaluation and reporting dashboard
- **`integration.spec.ts`** - Cross-browser and integration tests

### What's Being Tested

#### Demo Features
- ✅ Action Plan approval banners for high-risk scenarios
- ✅ Showcase SSH lateral movement detection rule 
- ✅ Timeline items with enhanced clickability
- ✅ Mock evaluation metrics (p50, p95, TPR, FPR, Coverage)
- ✅ Graph legend entries for ATT&CK techniques

#### Core Functionality  
- ✅ Page navigation and loading
- ✅ Incident details and management
- ✅ Detection rule creation and editing
- ✅ Evaluation dashboard metrics
- ✅ Responsive design across viewports
- ✅ Error handling and graceful degradation

## Running Tests

### Prerequisites
- Node.js 18+
- Running development server (`npm run dev`)

### Basic Commands

```bash
# Run all tests
npm run test

# Run tests with browser UI
npm run test:ui

# Run tests in headed mode (visible browser)
npm run test:headed

# Run specific test file
npx playwright test smoke.spec.ts

# Debug tests
npm run test:debug
```

### Test Configurations

Tests are configured to run against:
- **Browsers**: Chromium, Firefox, WebKit
- **Base URL**: http://localhost:3000
- **Parallel execution**: Yes (6 workers)
- **Retries**: 2 on CI, 0 locally

## Test Data & Mocks

Tests rely on:
- Mock incident data (`INC-2024-001`)
- Feature flags in `ui/lib/flags.ts`
- Demo showcase rule data
- Evaluation metrics from the dashboard

## CI/CD Integration

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main`
- Only when UI files change (`ui/**`)

## Browser Support

Tests verify compatibility across:
- ✅ **Desktop Chrome** (Chromium)
- ✅ **Desktop Firefox** 
- ✅ **Desktop Safari** (WebKit)
- ✅ **Mobile viewports** (375px, 768px, 1024px)

## Debugging Test Failures

1. **Run with UI mode**: `npm run test:ui`
2. **Check screenshots**: `test-results/` directory
3. **View traces**: Available in HTML reporter
4. **Debug mode**: `npm run test:debug`

## Adding New Tests

1. Create `.spec.ts` file in `tests/` directory
2. Follow naming convention: `feature-name.spec.ts`
3. Use Page Object Model for complex interactions
4. Include both positive and negative test cases
5. Test across different viewport sizes

## Feature Flags

Tests respect the demo feature flags in `ui/lib/flags.ts`:
- `forceHighRiskApprovalBanner` - Shows approval banners
- `seedShowcaseRule` - Adds demo detection rule
- `emphasizeTimelineClicks` - Enhances timeline interactions  
- `mockEvalNumbers` - Shows stable evaluation metrics

## Performance Considerations

- Tests timeout after 30 seconds by default
- Network requests can be mocked for stability
- Screenshots only captured on failure
- Parallel execution for faster feedback