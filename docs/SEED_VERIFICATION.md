# Verify local seed data

From `backend/`, after applying migrations, run:

```sh
python manage.py verify_seed_data
python manage.py verify_seed_data --scope curriculum
python manage.py verify_seed_data --scope dashboard
```

The default `all` scope checks both sets. This command only reads the database;
it never creates demo accounts, resets passwords, or repairs records. Its checks
do not use Redis; normal Django startup may still probe Redis according to the
environment settings. It is safe to repeat. Exit status 0 means every invariant passed;
status 1 means validation failed. Each `FAIL:` diagnostic identifies the record
and expected/actual count. Django reports connection or migration errors normally.

Curriculum expectations come from `seed_lessons`: one global lesson per defined
slug and exactly one of each required exercise title. Dashboard checks cover the
five demo users, five demo lessons/exercises, expected completed progress for
Alice/Bob/Charlie, Alice's active demo certificate, and the representative solved
issue/merged-PR relationship used by charts. Extra contributor data is allowed.
This is a structural smoke check, not a full content checksum, Redis leaderboard
check, or production integrity audit. Dashboard fixture names live alongside the
verification command; update them if `seed_dashboard` changes its demo dataset.

For a **disposable local database**, populate missing data with:

```sh
python manage.py seed_lessons
python manage.py seed_dashboard
python manage.py verify_seed_data
```

The seed commands mutate data and create/reset publicly documented demo accounts;
do not run them against production. Duplicate exercises need manual investigation:
verification deliberately leaves them intact. Running only one seed command is
supported by selecting its matching verification scope.
