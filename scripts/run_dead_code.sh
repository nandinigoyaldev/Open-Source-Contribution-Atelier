#!/bin/bash
# Run dead code detection

echo "🔍 Running dead code detection..."
echo "================================="

cd "$(dirname "$0")/../.."

# Run Python dead code detection
echo "📊 Detecting dead Python code..."
python backend/scripts/dead_code_detector.py --format md --output dead_code_report.md

# Display summary
echo ""
echo "📊 Summary:"
grep -A 10 "## 📊 Summary" dead_code_report.md || echo "No summary found"

echo ""
echo "✅ Report saved to dead_code_report.md"