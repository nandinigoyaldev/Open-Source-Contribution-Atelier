import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "compose_smoke.sh"
BASH = shutil.which("bash")

FAKE_DOCKER = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
case "$*" in
  *" config --services"*) printf 'db\nbackend\nfrontend\n' ;;
  *" logs "*) echo "fake logs for: $*" ;;
esac
exit 0
"""

# Succeeds for every URL unless it contains FAKE_FAIL_URL.
FAKE_CURL = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in
    http*) url="$arg" ;;
  esac
done
case "$url" in
  *"$FAKE_FAIL_URL"*) [ -n "$FAKE_FAIL_URL" ] && exit 22 ;;
esac
exit 0
"""


def _write_exec(path, body):
    path.write_text(body, newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@unittest.skipUnless(BASH, "bash is required")
class TestComposeSmokeScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = self.tmp / "docker.log"
        _write_exec(self.tmp / "docker", FAKE_DOCKER)
        _write_exec(self.tmp / "curl", FAKE_CURL)
        _write_exec(self.tmp / "sleep", "#!/bin/sh\nexit 0\n")
        _write_exec(
            self.tmp / "python3",
            f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
        )

    def run_script(self, fail_url=""):
        env = dict(os.environ)
        env.update(
            PATH=f"{self.tmp.as_posix()}{os.pathsep}{env['PATH']}",
            FAKE_LOG=self.log.as_posix(),
            FAKE_FAIL_URL=fail_url,
            SMOKE_TIMEOUT="3",
        )
        return subprocess.run(
            [BASH, SCRIPT.as_posix()], env=env, capture_output=True, text=True
        )

    def docker_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_passes_and_cleans_up(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Smoke test passed.", result.stdout)
        self.assertTrue(any(" down -v" in c for c in self.docker_calls()))

    def test_failure_names_service_prints_logs_and_cleans_up(self):
        result = self.run_script(fail_url=":8000/")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL [backend]", result.stderr)
        self.assertIn("fake logs for", result.stderr)
        self.assertTrue(
            any(" logs " in c and "backend" in c for c in self.docker_calls())
        )
        self.assertTrue(any(" down -v" in c for c in self.docker_calls()))

    def test_does_not_use_real_credentials(self):
        text = SCRIPT.read_text()
        self.assertIn("secrets.token_urlsafe", text)
        self.assertIn("trap cleanup EXIT", text)


if __name__ == "__main__":
    unittest.main()
