# Container Image Scanning

`.github/workflows/image-scan.yml` builds the backend image and scans it with
[Trivy](https://trivy.dev) for known vulnerabilities in OS packages and Python
packages. The result is written to the workflow summary, and the job fails only
for the severities listed in the policy below.

## What is scanned

The image is built from the root `Dockerfile`, with no extra build arguments or
target. That is the file the Hugging Face Space builds (`sdk: docker` and
`app_port: 7860` in the `README.md` front matter), so the scanned image is the
deployed one. `backend/Dockerfile` is the Compose and development image and is
not scanned here.

| When | Why |
| --- | --- |
| Pull request that touches `Dockerfile`, `backend/requirements*.txt`, `backend/pyproject.toml`, `.trivyignore`, the scan scripts or the workflow | Catch a bad dependency or base image change before it merges |
| Push to `main` | Check what was actually merged |
| Every Monday 03:15 UTC | New CVEs are published against code that did not change |
| Manual run (`workflow_dispatch`) | Re-check after a fix or an exception change |

The job needs no secrets, has `contents: read` only, and is limited to 25
minutes (the Trivy step to 10). Raw JSON output is kept as the `trivy-report`
artifact for 14 days.

## Severity policy

Trivy is run with `--severity HIGH,CRITICAL`, `--ignore-unfixed` and the
vulnerability scanner only (no secret or misconfiguration scanning).

| Finding | Result |
| --- | --- |
| CRITICAL, fix available | The job fails |
| HIGH, fix available | The job passes. The finding is in the summary table and shows as a warning annotation |
| Any severity, no fix available yet | Not reported (`--ignore-unfixed`). The weekly run picks it up once a fix exists |
| MEDIUM, LOW, UNKNOWN | Not reported |
| Finding listed in `.trivyignore` and not expired | Not reported |
| Trivy could not run or produced no usable report (for example the vulnerability database could not be downloaded) | The job fails. Re-run it |

The failing severities are the `FAIL_SEVERITIES` variable at the top of the
workflow (`CRITICAL`). Setting it to `HIGH,CRITICAL` makes HIGH findings fail
too. Change the variable and this table in the same pull request.

HIGH findings do not block a merge but they are not optional: `SECURITY.md`
gives HIGH a 7 day patch target and CRITICAL 48 hours. A warning that is still
there a week later should become an issue, or a reviewed exception.

## Reading the results

Open the run and look at the workflow summary. It has a count per severity and
a table with the ID (linked to the advisory), package, installed version, fixed
version and title, CRITICAL first. At most 100 rows are shown, the artifact has
the full list.

Typical fixes:

- Package from `backend/requirements.txt`: bump it to the fixed version.
- OS package or Python itself: rebuild so the base image is pulled again. The
  `python:3.11-slim` tag moves, a rebuild is often enough. If it is not,
  see whether a newer tag or digest is available.

## Exceptions

If a finding cannot be fixed right now, add it to `.trivyignore` at the
repository root. Exceptions are reviewed like code, so the pull request that adds
one is the review.

Each entry looks like this (the ID is made up):

```text
# Reason: vendor confirmed the vulnerable code path is not reachable in this image
# Owner: @github-handle  Ref: https://github.com/<owner>/<repo>/issues/<n>
CVE-2099-00000 exp:2099-01-31
```

Rules, checked by `scripts/ci/check-trivyignore.sh` on every run:

1. One ID per line, followed by `exp:YYYY-MM-DD`.
2. A `# Reason:` line and a `# Owner:` line in the comment block directly above
   the entry (a blank line ends the block). The reason says why the
   finding is acceptable, not just that it is. Put a link to a tracking issue in `Ref:` when
   there is one.
3. The expiry is at most 90 days from the day you add or renew the entry. Trivy
   itself stops applying an entry after its expiry date, so an
   exception cannot go stale silently: the finding comes back and the job
   fails or warns according to the policy.
4. The pull request description says what the finding is and why it is being
   accepted, and a maintainer approves it. `.trivyignore` is listed in the
   workflow's path filter, so changing it re-runs the scan.

An expired entry that is still in the file gives a warning annotation. Remove
it, or re-review it and set a new date, with a new reason if the situation changed.

Prefer fixing over ignoring. An exception for a finding that has a fix
available should be short and should name the blocker (for example a package
that has not released a compatible version yet).

## False positives

A finding is a false positive when the vulnerable code is not present or not
reachable in this image, or the scanner matched the wrong package or version.

1. Confirm it. Read the advisory, check the package and version in the summary
   table, and check how the image uses that package. Only the final (runtime)
   stage is scanned, so a package that exists only in the build stage is never
   reported.
2. Add a `.trivyignore` entry as described above. In `Reason:` write what you
   checked, for example "advisory affects the Windows installer only, image is Linux".
3. If the scanner data is wrong rather than our usage, report it to the
   [Trivy](https://github.com/aquasecurity/trivy/discussions) or
   advisory source as well, so that the entry can be removed when it is corrected.
4. Keep the expiry short. When it passes, check whether the data was corrected
   before renewing.

Do not disable the scan, lower the severities, or add `skip-dirs` or
`skip-files` to hide a finding. Those changes hide every finding in that area
and are not a replacement for an entry with a reason.

`backend/scripts/vuln-allowlist.json` is a separate list, used by `make` and
`backend/scripts/check_dependency_allowlist.py` for pip-audit and npm audit
reports. It is not read by the image scan. If a CVE shows up in both places,
it needs an entry in each.

## Dependency license review in release reports

`backend/scripts/check_dependency_allowlist.py` embeds a deterministic
`dependency_licenses` summary in `vuln-report-consolidated.json` covering both
frontend (`package-lock.json`, `frontend/package-lock.json`) and backend
(`backend/requirements*.txt`, `services/notifications_worker/requirements.txt`)
dependencies without modifying dependency resolution. You can also generate or
gate the license summary directly:

```bash
# Produce reproducible JSON and check for unknown/disallowed licenses
python scripts/release_license_report.py --output release-license-report.json --fail-on-disallowed

# Strict mode (fail on both UNKNOWN and disallowed licenses)
python scripts/release_license_report.py --strict
```

Review any entries listed under `disallowed_packages`, `unknown_packages`, or
`review_required` before approving a release. Unknown backend package metadata
in environments without installed wheels can be supplied via
`--python-licenses-json`.

## Run the scan locally

You need Docker and [Trivy](https://trivy.dev/docs/latest/getting-started/installation/).
From the repository root:

```bash
docker build -f Dockerfile -t atelier-backend:scan .

trivy image \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --ignorefile .trivyignore \
  --format json --output trivy-report.json \
  --exit-code 0 \
  atelier-backend:scan

# Same summary and pass/fail decision as the workflow (needs jq)
FAIL_SEVERITIES=CRITICAL bash scripts/ci/trivy-summary.sh trivy-report.json
echo "exit code: $?"

# Check the format of your .trivyignore entries
bash scripts/ci/check-trivyignore.sh .trivyignore
```

Without a local Trivy install, run it in a container instead:

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/work -w /work \
  aquasec/trivy:0.70.0 image \
  --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed \
  --ignorefile .trivyignore --format json --output trivy-report.json \
  --exit-code 0 atelier-backend:scan
```

The workflow uses the Trivy version that its pinned action installs, so a
local run with a different version can report slightly different results.

## Limits

- Only vulnerabilities with a published fix are reported, by design. An unfixed
  CRITICAL does not fail the job.
- The scan sees what is in the image at build time. The `python:3.11-slim` tag is
  not pinned to a digest, so two builds of the same commit can differ.
- Results depend on the Trivy vulnerability database, which the job downloads on
  each run. If that download fails the job fails (see the policy table).
- The Trivy action is pinned to a full commit SHA with the version in a comment,
  following the pinning policy for third-party actions (`docs/ci/action-pinning.md`,
  added in #3167). Update the SHA and the comment together.
