#!/bin/bash
# verify_pr.sh
# Automates the checking of an open-source PR locally.

if [ -z "$1" ]; then
  echo "Usage: ./verify_pr.sh <pr-number>"
  echo "Example: ./verify_pr.sh 142"
  exit 1
fi

PR_NUMBER=$1

echo "==========================================="
echo " Fetching PR #$PR_NUMBER from origin..."
echo "==========================================="
# Fetch the PR branch into a local branch called pr-<number>
git fetch origin pull/$PR_NUMBER/head:pr-$PR_NUMBER
if [ $? -ne 0 ]; then
  echo "❌ Error fetching PR #$PR_NUMBER. Does it exist?"
  exit 1
fi

git checkout pr-$PR_NUMBER

echo ""
echo "==========================================="
echo " Running Frontend Checks..."
echo "==========================================="
cd frontend
echo "-> Installing frontend dependencies..."
npm install > /dev/null 2>&1
echo "-> Running frontend linter..."
npm run lint
if [ $? -ne 0 ]; then
  echo "❌ Frontend Linter Failed! Please fix before merging."
  exit 1
fi

echo "-> Running frontend type checker..."
npm run tsc
if [ $? -ne 0 ]; then
  echo "❌ Frontend Type Checker Failed! Please fix before merging."
  exit 1
fi

echo "-> Running frontend tests..."
npm run test
if [ $? -ne 0 ]; then
  echo "❌ Frontend Tests Failed! Please fix before merging."
  exit 1
fi
cd ..

echo ""
echo "==========================================="
echo " Running Backend Checks..."
echo "==========================================="
cd backend
echo "-> Activating virtual environment & installing deps..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

echo "-> Running backend tests..."
python manage.py test
if [ $? -ne 0 ]; then
  echo "❌ Backend Tests Failed! Please fix before merging."
  exit 1
fi
cd ..

echo ""
echo "==========================================="
echo " ✅ All Checks Passed Successfully! ✅"
echo "==========================================="
echo "The PR code works perfectly. You can now merge it!"
echo "Switching back to main branch..."
git checkout main
