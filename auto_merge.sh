#!/bin/bash
set -e

# get all open PRs
prs=$(gh pr list --json number -q '.[].number')

for pr in $prs; do
    echo "Processing PR $pr"
    
    # Try to squash and merge directly first
    if gh pr merge $pr --squash --admin; then
        echo "Successfully merged PR $pr"
        continue
    fi
    
    echo "PR $pr failed to merge directly. Attempting to resolve conflicts..."
    
    # Get the branch name for this PR
    branch=$(gh pr view $pr --json headRefName -q '.headRefName')
    
    # Checkout the PR locally using gh
    gh pr checkout $pr
    
    # Attempt to merge main, keeping our (PR's) changes for any conflicts
    if ! git merge origin/main -X ours --no-edit; then
        echo "Merge failed even with -X ours, resolving forcefully..."
        # If there are still conflicts (e.g. deleted by us, modified by them)
        git add .
        git commit -m "Auto-resolve conflicts" || true
    fi
    
    # Push back to the PR branch
    git push origin HEAD:$branch
    
    # Try merging again
    if gh pr merge $pr --squash --admin; then
        echo "Successfully resolved and merged PR $pr"
    else
        echo "Still failed to merge PR $pr after resolving conflicts"
    fi
done

echo "Done."
