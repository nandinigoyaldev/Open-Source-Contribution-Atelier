#!/bin/bash
# Pre-push verification script for Open-Source-Contribution-Atelier

set -e # Exit immediately if a command exits with a non-zero status

# Color codes for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==> Starting Pre-push Verification Checklist <==${NC}\n"

# 1. Frontend Lint
echo "Checking frontend code linting..."
(cd frontend && npm run lint)
echo -e "${GREEN}✓ Frontend Lint Passed!${NC}\n"

# 2. Frontend Format Check
echo "Checking frontend code formatting..."
(cd frontend && npm run format:check)
echo -e "${GREEN}✓ Frontend Formatting Check Passed!${NC}\n"

# 3. Frontend Tests
echo "Running frontend tests..."
(cd frontend && npm run test)
echo -e "${GREEN}✓ Frontend Tests Passed!${NC}\n"

# 4. Backend Formatting Check
echo "Checking backend code formatting..."
(cd backend && black --check .)
echo -e "${GREEN}✓ Backend Formatting Check Passed!${NC}\n"

# 5. Backend Tests
echo "Running backend tests..."
(cd backend && pytest)
echo -e "${GREEN}✓ Backend Tests Passed!${NC}\n"

echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}🎉 All pre-push checks passed successfully!${NC}"
echo -e "${GREEN}===========================================${NC}"
