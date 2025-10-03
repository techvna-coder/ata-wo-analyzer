#!/bin/bash
# Run all tests with coverage report

set -e

echo "================================"
echo "Running ATA WO Analyzer Tests"
echo "================================"
echo ""

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests
echo "Running unit tests..."
pytest tests/ -v \
    --cov=core \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-report=xml

echo ""
echo "================================"
echo "Test Results Summary"
echo "================================"

# Display coverage summary
coverage report

echo ""
echo "HTML coverage report: htmlcov/index.html"
echo ""

# Check coverage threshold
coverage report --fail-under=70

echo ""
echo "✅ All tests passed!"
