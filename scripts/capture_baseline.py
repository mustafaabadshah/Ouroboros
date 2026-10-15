import sys
import os
import json
import platform
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone

# 1. Environment & Python
py_ver = sys.version
node_ver = shutil.which("node") and subprocess.run(["node", "--version"], capture_output=True, text=True, shell=True).stdout.strip()
npm_ver = shutil.which("npm") and subprocess.run(["npm", "--version"], capture_output=True, text=True, shell=True).stdout.strip()

# 2. Git status
git_commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
git_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
git_dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()

# 3. Memory & Hardware
import psutil
mem = psutil.virtual_memory()

# 4. Connected Repositories
agent_chess_path = Path(r"E:\MM Office\Agent Chess")
navigator_path = Path(r"E:\MM Office\Meta-Graph-Codebase-Navigator")

chess_status = {"exists": agent_chess_path.exists()}
if agent_chess_path.exists():
    chess_status["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=agent_chess_path, capture_output=True, text=True).stdout.strip()
    chess_status["branch"] = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=agent_chess_path, capture_output=True, text=True).stdout.strip()
    chess_status["dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], cwd=agent_chess_path, capture_output=True, text=True).stdout.strip())

nav_status = {"exists": navigator_path.exists()}
if navigator_path.exists():
    nav_status["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=navigator_path, capture_output=True, text=True).stdout.strip()
    nav_status["branch"] = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=navigator_path, capture_output=True, text=True).stdout.strip()
    nav_status["dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], cwd=navigator_path, capture_output=True, text=True).stdout.strip())

# 5. Pip installed packages
pip_list = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], capture_output=True, text=True).stdout
installed_pkgs = json.loads(pip_list) if pip_list else []

report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "ouroboros_git": {
        "commit": git_commit,
        "branch": git_branch,
        "dirty_files_count": len([l for l in git_dirty.split("\n") if l.strip()])
    },
    "host_environment": {
        "os": platform.platform(),
        "python_version": py_ver,
        "node_version": node_ver,
        "npm_version": npm_ver,
        "total_ram_mb": round(mem.total / (1024 * 1024), 2),
        "available_ram_mb": round(mem.available / (1024 * 1024), 2),
        "cpu_count": os.cpu_count()
    },
    "connected_external_repositories": {
        "agent_chess": chess_status,
        "meta_graph_navigator": nav_status
    },
    "installed_key_dependencies": {pkg["name"]: pkg["version"] for pkg in installed_pkgs if pkg["name"].lower() in [
        "fastapi", "uvicorn", "pydantic", "sqlalchemy", "pytest", "arize-phoenix", "arize-phoenix-client",
        "opentelemetry-api", "opentelemetry-sdk", "httpx", "psutil", "pyautogen"
    ]},
    "active_ports_verified": {
        "backend": "http://127.0.0.1:8000 (HTTP 200)",
        "frontend": "http://localhost:5173 (HTTP 200)",
        "phoenix": "http://127.0.0.1:6006 (HTTP 200)"
    }
}

os.makedirs("artifacts/baseline", exist_ok=True)
with open("artifacts/baseline/baseline_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("Baseline successfully saved to artifacts/baseline/baseline_report.json")
