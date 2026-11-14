# Frontend npm cache in CI

Frontend dependency jobs use `actions/setup-node@v4` with `cache: npm` and
`cache-dependency-path: frontend/package-lock.json`. API type generation and the
performance budget now use the same download-cache configuration as frontend
tests, accessibility, quality gates, release readiness, audit and source maps.

setup-node's key includes runner OS, architecture, package manager and lockfile
hash. A changed lockfile therefore selects a different key.
API type freshness also triggers on lockfile-only PRs, so dependency changes
cannot silently skip that job.
Only npm's package download cache is saved; `node_modules`, build outputs and credentials are not
cached. Install steps run unconditionally on both hits and misses. No cache-hit
condition skips installation, tests, type generation or budget enforcement.

The performance workflow's base-branch build can reuse downloaded tarballs while
still installing its own dependency tree in `base/frontend`. Different dependency
versions are resolved and verified by npm, not supplied as cached node_modules.
The existing installation commands are preserved, including their documented
lockfile-drift limitations; caching does not make an inconsistent lockfile valid.

To verify on GitHub, inspect the setup-node step for the lockfile-derived key and
hit/miss message, then confirm the install step ran. Use a branch with a changed
lockfile to verify a new key and cold installation; rerun to exercise a hit.
Failure output and all existing gates must remain visible in both runs.

Reference: [setup-node caching documentation](https://github.com/actions/setup-node/tree/v4#caching-global-packages-data).
