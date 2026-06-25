#!/bin/bash
echo "Creating 50 issues..."
jq -c '.[]' issues.json | while read i; do
  TITLE=$(echo $i | jq -r '.title')
  BODY=$(echo $i | jq -r '.body')
  LABEL=$(echo $i | jq -r '.label')
  TYPE=$(echo $i | jq -r '.type')
  
  # Format body with ssoc26 checkbox
  FULL_BODY="> Please checkmark ssoc26 if you are contributing under that.\n- [ ] ssoc26\n\n$BODY"
  
  # Add ssoc tag directly as requested, plus the difficulty label, plus type
  echo "Creating: $TITLE [$LABEL, $TYPE, SSoC26]"
  gh issue create --title "$TITLE" --body "$FULL_BODY" --label "$LABEL" --label "$TYPE" --label "SSoC26"
  sleep 1 # Prevent API rate limits
done
echo "Done!"
