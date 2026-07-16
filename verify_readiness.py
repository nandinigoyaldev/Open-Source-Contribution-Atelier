#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Fix terminal encoding issues on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ANSI Escape Sequences for beautiful terminal outputs
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
NC = "\033[0m"

print(f"{BLUE}{BOLD}===================================================={NC}")
print(f"{BLUE}{BOLD}   🚀 CONTRIBUTOR PRE-FLIGHT READINESS CHECKLIST 🚀   {NC}")
print(f"{BLUE}{BOLD}===================================================={NC}\n")

def check_step(name, success_msg, fail_msg, check_fn):
    print(f"🔄 Checking: {BOLD}{name}{NC}...", end="", flush=True)
    success, details = check_fn()
    # Backspace to overwrite the loader
    print("\r", end="")
    if success:
        print(f"✅ {GREEN}{BOLD}PASSED{NC} | {name}: {details}")
        return True
    else:
        print(f"❌ {RED}{BOLD}FAILED{NC} | {name}: {details}")
        print(f"   💡 {YELLOW}Tip: {fail_msg}{NC}\n")
        return False

# --- Checks definitions ---

def check_python():
    version = sys.version.split()[0]
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 9:
        return True, f"Python {version} detected."
    return False, f"Python {version} detected, but 3.9+ is recommended."

def check_node():
    try:
        node_version = subprocess.check_output(["node", "--version"], text=True).strip()
        major = int(node_version.lstrip("v").split(".")[0])
        if major >= 20:
            return True, f"Node.js {node_version} detected."
        return False, f"Node.js {node_version} detected, but v20+ is required."
    except FileNotFoundError:
        return False, "Node.js is not installed or not in PATH."

def get_venv_python():
    venv_dir = Path("backend/.venv")
    windows_path = venv_dir / "Scripts" / "python.exe"
    unix_path = venv_dir / "bin" / "python"
    if windows_path.exists():
        return windows_path
    if unix_path.exists():
        return unix_path
    return None

def check_venv():
    # Check if .venv directory exists in backend/
    if get_venv_python() is not None:
        return True, "Virtual environment (.venv) exists in backend/"
    return False, "Virtual environment not found in backend/.venv"

def check_env_files():
    backend_env = Path("backend/.env")
    frontend_env = Path("frontend/.env")
    missing = []
    if not backend_env.exists():
        missing.append("backend/.env")
    if not frontend_env.exists():
        missing.append("frontend/.env")
    if missing:
        return False, f"Missing files: {', '.join(missing)}"
    return True, "All local .env configuration files are present."

def check_backend_migrations():
    # If venv Python is available, check pending migrations
    python_path = get_venv_python()
    if python_path is None:
        python_path = Path("python" if sys.platform == "win32" else "python3") # fallback
    try:
        res = subprocess.run(
            [str(python_path), "backend/manage.py", "showmigrations", "--plan"],
            capture_output=True, text=True, check=True
        )
        unapplied = [line for line in res.stdout.splitlines() if "[ ]" in line]
        if unapplied:
            return False, f"There are {len(unapplied)} unapplied migrations."
        return True, "All database migrations are applied."
    except Exception as e:
        return False, f"Could not check migrations: {e}"

def check_frontend_deps():
    node_modules = Path("frontend/node_modules")
    if node_modules.exists():
        return True, "frontend/node_modules installed."
    return False, "frontend dependencies are not installed."

def check_prepush_checklist():
    print(f"\n{BLUE}{BOLD}--- Running Quick Code Format and Lint Dry-Run ---{NC}")
    
    # 1. Frontend Formatting Check
    try:
        npm_exe = "npm.cmd" if sys.platform == "win32" else "npm"
        subprocess.check_output([npm_exe, "--prefix", "frontend", "run", "format:check"], stderr=subprocess.STDOUT)
        print(f"   ✨ {GREEN}Frontend Prettier format check passed.{NC}")
    except subprocess.CalledProcessError:
        print(f"   ⚠️  {YELLOW}Frontend formatting needs correction. Run 'npm run format' in frontend/.{NC}")
        
    # 2. Backend Formatting Check
    try:
        python_path = get_venv_python()
        black_cmd = [str(python_path), "-m", "black", "--check", "backend/"] if python_path is not None else ["black", "--check", "backend/"]
        subprocess.check_output(black_cmd, stderr=subprocess.STDOUT)
        print(f"   ✨ {GREEN}Backend Black format check passed.{NC}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"   ⚠️  {YELLOW}Backend formatting needs correction. Run 'black .' in backend/.{NC}")

    return True, "Finished running formatting dry-run."

# Run all checks
steps = [
    ("Python Version", "Ensure Python 3.9+ is installed.", check_python),
    ("Node.js Version", "Install Node.js version 20+ from nodejs.org", check_node),
    ("Virtual Environment", "Create one: 'cd backend && python -m venv .venv'", check_venv),
    ("Local Settings (.env)", "Copy .env.example files to .env in backend/ and frontend/", check_env_files),
    ("Database Migrations", "Apply migrations: 'cd backend && python manage.py migrate'", check_backend_migrations),
    ("Frontend Dependencies", "Install packages: 'cd frontend && npm install'", check_frontend_deps),
]

all_passed = True
for name, tip, fn in steps:
    if not check_step(name, "", tip, fn):
        all_passed = False

check_prepush_checklist()

print(f"\n{BLUE}{BOLD}===================================================={NC}")
if all_passed:
    print(f"🎉 {GREEN}{BOLD}CONGRATULATIONS! Your environment is ready to push!{NC}")
    print(f"🚀 Feel free to open your Pull Request on GitHub.")
else:
    print(f"⚠️  {YELLOW}{BOLD}Some readiness checks did not pass.{NC}")
    print("👉 Please follow the tips above to fix the issues before pushing.")
print(f"{BLUE}{BOLD}===================================================={NC}")

sys.exit(0 if all_passed else 1)
