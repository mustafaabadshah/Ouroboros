"""
Ouroboros Autonomous Chat History Synchronization & Backup Engine
Prevents conversation loss between Antigravity IDE and Antigravity 2.0 Desktop.
Mirrors transcripts to versioned markdown in docs/chat_history/.
Supports single-run and continuous daemon/watcher mode.
"""

import os
import sys
import json
import sqlite3
import shutil
import base64
import time
from pathlib import Path

WORKSPACE = Path(r"E:\MM Office\Ouroboros")
DOCS_HISTORY = WORKSPACE / "docs" / "chat_history"

DIR_DESKTOP = Path(r"C:\Users\Mustafa Badshah\.gemini\antigravity")
DIR_IDE = Path(r"C:\Users\Mustafa Badshah\.gemini\antigravity-ide")
IDE_VSCDB = Path(r"C:\Users\Mustafa Badshah\AppData\Roaming\Antigravity IDE\User\globalStorage\state.vscdb")
APP_STORAGE = Path(r"C:\Users\Mustafa Badshah\AppData\Roaming\Antigravity\app_storage.json")

def ensure_dirs():
    DOCS_HISTORY.mkdir(parents=True, exist_ok=True)

def sync_conversation(cid: str, source_is_ide: bool):
    src_dir = DIR_IDE if source_is_ide else DIR_DESKTOP
    dst_dir = DIR_DESKTOP if source_is_ide else DIR_IDE

    # 1. Sync .db file
    src_db = src_dir / "conversations" / f"{cid}.db"
    dst_db = dst_dir / "conversations" / f"{cid}.db"
    if src_db.exists():
        if not dst_db.exists() or src_db.stat().st_mtime > dst_db.stat().st_mtime:
            dst_db.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_db, dst_db)
            except Exception:
                pass

    # 2. Sync brain directory
    src_brain = src_dir / "brain" / cid
    dst_brain = dst_dir / "brain" / cid
    if src_brain.exists() and not dst_brain.exists():
        dst_brain.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(src_brain, dst_brain, dirs_exist_ok=True)
        except Exception:
            pass

    # 3. Export to Markdown in workspace docs
    transcript = src_brain / ".system_generated" / "logs" / "transcript.jsonl"
    if transcript.exists():
        export_transcript_to_markdown(cid, transcript)

def export_transcript_to_markdown(cid: str, transcript_path: Path):
    turns = []
    current_user = None
    current_ai = []
    
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    t = data.get("type")
                    if t == "USER_INPUT":
                        if current_user is not None:
                            turns.append((current_user, current_ai))
                        content = data.get("content", "")
                        if "<USER_REQUEST>" in content:
                            s = content.find("<USER_REQUEST>") + len("<USER_REQUEST>")
                            e = content.find("</USER_REQUEST>")
                            if e != -1:
                                content = content[s:e].strip()
                        current_user = content
                        current_ai = []
                    elif t == "PLANNER_RESPONSE" and data.get("content"):
                        c = data.get("content", "").strip()
                        if c:
                            current_ai.append(c)
                except Exception:
                    pass
        if current_user is not None:
            turns.append((current_user, current_ai))
    except Exception:
        return

    if not turns:
        return

    md_file = DOCS_HISTORY / f"chat_{cid[:8]}.md"
    try:
        with open(md_file, "w", encoding="utf-8") as out:
            out.write(f"# Chat Session Backup: `{cid}`\n\n")
            out.write(f"> **Conversation ID:** `{cid}`  \n")
            out.write(f"> **Last Synced:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
            out.write(f"> **Total Turns:** {len(turns)}  \n\n")
            out.write("---\n\n")

            for idx, (req, resps) in enumerate(turns, 1):
                out.write(f"## Turn {idx}\n\n")
                out.write("### 👤 User:\n\n```markdown\n" + req + "\n```\n\n")
                out.write("### 🤖 Assistant:\n\n")
                if resps:
                    out.write(resps[-1] + "\n\n")
                out.write("---\n\n")
    except Exception:
        pass

def run_sync():
    ensure_dirs()
    ide_convs = {p.stem for p in (DIR_IDE / "conversations").glob("*.db")} if (DIR_IDE / "conversations").exists() else set()
    desktop_convs = {p.stem for p in (DIR_DESKTOP / "conversations").glob("*.db")} if (DIR_DESKTOP / "conversations").exists() else set()

    for cid in ide_convs:
        sync_conversation(cid, source_is_ide=True)

    for cid in desktop_convs:
        sync_conversation(cid, source_is_ide=False)

def main():
    watch_mode = "--watch" in sys.argv
    run_sync()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Initial conversation backup complete.")
    if watch_mode:
        print("Watching for conversation changes every 30 seconds...")
        while True:
            try:
                time.sleep(30)
                run_sync()
            except KeyboardInterrupt:
                break
            except Exception as e:
                time.sleep(5)

if __name__ == "__main__":
    main()
