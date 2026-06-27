#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Creating 50 issues from $DIR/issues.json..."

if [ ! -f "$DIR/issues.json" ]; then
  echo "Error: $DIR/issues.json not found. Run 'python3 $DIR/generate_issues.py' first."
  exit 1
fi

jq -c '.[]' "$DIR/issues.json" | while read i; do
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
