#!/bin/bash
cd /path/to/backend
source venv/bin/activate
python scripts/backup_db.py >> log/backup.log 2>&1