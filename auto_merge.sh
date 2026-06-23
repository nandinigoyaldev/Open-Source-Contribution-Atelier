#!/bin/bash
set -e

prs=$(gh pr list --json number -q '.[].number')

for pr in $prs; do
    echo "Processing PR $pr"
    
    if gh pr merge $pr --squash --admin; then
        echo "Successfully merged PR $pr"
        continue
    fi
    
    echo "PR $pr failed to merge directly. Attempting to resolve conflicts..."
    
    # Get the branch name for this PR
    branch=$(gh pr view $pr --json headRefName -q '.headRefName')
    
    # clean up any old branch
    git checkout main
    git pull origin main
    git branch -D $branch || true
    
    # Checkout the PR locally using gh
    gh pr checkout $pr
    
    # ensure clean tree
    git add . && git commit -m "format" || true
    
    # Merge origin/main
    if ! git merge origin/main -X ours --no-edit; then
        echo "Merge failed even with -X ours, resolving forcefully..."
        git add .
        git commit -m "Auto-resolve conflicts" || true
    fi
    
    # push to the fork
    remote=$(git config --get branch.$(git branch --show-current).remote)
    git push $remote HEAD
    
    sleep 5
    
    # Try merging again
    if gh pr merge $pr --squash --admin; then
        echo "Successfully resolved and merged PR $pr"
    else
        echo "Still failed to merge PR $pr after resolving conflicts"
    fi
done

echo "Done."
