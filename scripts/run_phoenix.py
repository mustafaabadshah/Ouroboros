"""
Arize Phoenix standalone runner for Project Ouroboros.
Launches the Phoenix observability UI and OTLP collector on http://127.0.0.1:6006 using phoenix serve.
"""
import sys
import os

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["PHOENIX_PORT"] = "6006"
os.environ["PHOENIX_HOST"] = "127.0.0.1"

if __name__ == "__main__":
    print("[Phoenix] Launching Arize Phoenix via phoenix serve on http://127.0.0.1:6006 ...", flush=True)
    from phoenix.server.main import main
    sys.argv = ["phoenix", "serve"]
    main()
