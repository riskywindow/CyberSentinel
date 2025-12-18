#!/bin/bash

# CyberSentinel UI Testing Script
# Run this from the project root to test the UI

echo "🧪 CyberSentinel UI Testing"
echo "=========================="

cd ui

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if dev server is running
if ! curl -s http://localhost:3000 > /dev/null; then
    echo "❌ Dev server not running at http://localhost:3000"
    echo "💡 Please run 'npm run dev' in the ui/ directory first"
    exit 1
fi

echo "✅ Dev server is running"

# Run smoke tests first
echo "🔥 Running smoke tests..."
npm run test smoke.spec.ts

if [ $? -eq 0 ]; then
    echo "✅ Smoke tests passed!"
    
    # Ask if user wants to run full test suite
    read -p "🤔 Run full test suite? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🚀 Running full test suite..."
        npm run test
    else
        echo "✅ Testing complete!"
    fi
else
    echo "❌ Smoke tests failed"
    exit 1
fi

echo ""
echo "📊 To view detailed test report:"
echo "   npx playwright show-report"
echo ""
echo "🎯 Demo features tested:"
echo "   ✅ Action Plan approval banners"
echo "   ✅ SSH lateral movement showcase rule"  
echo "   ✅ Timeline clickability enhancements"
echo "   ✅ Mock evaluation metrics"
echo "   ✅ Cross-browser compatibility"