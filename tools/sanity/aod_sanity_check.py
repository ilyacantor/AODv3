#!/usr/bin/env python3
"""
AOD Sanity Test Harness - Read-Only, Agent-Proof

Detects violations of deterministic zombie spec, dual stores, hidden defaults,
fake timestamps, and anything that would let AOD appear to work while cheating.

Exit codes:
  0 = PASS (all checks passed)
  2 = FAIL (guardrail violated)
  3 = ERROR (script couldn't run)
"""

import os
import sys
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

BANNED_KEYWORDS = [
    "anomaly", "contamination", "isolationforest", "threshold", 
    "score", "probab", "confidence", "heuristic"
]

ACTIVITY_EVIDENCE_KEYWORDS = [
    "observed_at", "last_seen", "last_activity", "activity_evidence",
    "latest_activity_at", "last_login_at", "endpoint_last_seen"
]

DUAL_STORE_FOLDERS = ["data/", "snapshots/", "exports/", "tmp/", ".cache/"]
DB_EXTENSIONS = [".db", ".sqlite", ".sqlite3"]


def find_repo_root() -> Path:
    """Find repository root by looking for known markers."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists() or (current / "pyproject.toml").exists() or (current / "replit.md").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


def print_header(repo_root: Path):
    """Print header with timestamp and repo root."""
    print("=" * 60)
    print(f"AOD SANITY CHECK")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Repo Root: {repo_root}")
    print("=" * 60)
    print()


def check_storage_modality(repo_root: Path) -> tuple[bool, list[str]]:
    """
    Check 1: Storage modality audit (dual-store detection)
    
    Detect if AOD persists data in multiple places.
    """
    issues = []
    stores_found = []
    
    for folder in DUAL_STORE_FOLDERS:
        folder_path = repo_root / folder
        if folder_path.exists() and folder_path.is_dir():
            data_files = list(folder_path.glob("**/*.json")) + \
                        list(folder_path.glob("**/*.csv")) + \
                        list(folder_path.glob("**/*.parquet"))
            if data_files:
                stores_found.append(f"{folder} ({len(data_files)} data files)")
    
    db_files = []
    for ext in DB_EXTENSIONS:
        db_files.extend(repo_root.glob(f"**/*{ext}"))
    db_files = [f for f in db_files if ".venv" not in str(f) and "node_modules" not in str(f)]
    
    non_empty_dbs = []
    for db_file in db_files:
        if db_file.stat().st_size > 0:
            non_empty_dbs.append(str(db_file.relative_to(repo_root)))
    
    if non_empty_dbs:
        stores_found.append(f"SQLite DBs: {', '.join(non_empty_dbs)}")
    
    db_url_present = bool(os.environ.get("DATABASE_URL"))
    supabase_present = bool(os.environ.get("SUPABASE_URL"))
    
    if db_url_present:
        stores_found.append("DATABASE_URL env var (external DB)")
    if supabase_present:
        stores_found.append("SUPABASE_URL env var (external DB)")
    
    if len(stores_found) > 1:
        has_sqlite = any("SQLite" in s for s in stores_found)
        has_external = db_url_present or supabase_present
        has_file_store = any(any(f in s for f in DUAL_STORE_FOLDERS) for s in stores_found)
        
        if (has_sqlite and has_external) or (has_sqlite and has_file_store) or (has_external and has_file_store):
            issues.append(f"DUAL STORE DETECTED: {stores_found}")
    
    if stores_found and not issues:
        print(f"  INFO: Stores found: {stores_found}")
    
    return len(issues) == 0, issues


def check_deterministic_policy(repo_root: Path) -> tuple[bool, list[str]]:
    """
    Check 2: Deterministic-only policy scan (static)
    
    Grep for ML/anomaly keywords. Phase 0 = WARN only.
    """
    warnings = []
    
    src_path = repo_root / "src"
    if not src_path.exists():
        src_path = repo_root
    
    py_files = list(src_path.glob("**/*.py"))
    py_files = [f for f in py_files if ".venv" not in str(f) and "sanity" not in str(f)]
    
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            
            for i, line in enumerate(lines, 1):
                line_lower = line.lower()
                if line.strip().startswith("#"):
                    continue
                    
                for keyword in BANNED_KEYWORDS:
                    if keyword in line_lower:
                        rel_path = py_file.relative_to(repo_root)
                        warnings.append(f"  {rel_path}:{i} - '{keyword}' found")
                        break
        except Exception:
            pass
    
    if warnings:
        print(f"  WARNINGS (non-deterministic keywords found):")
        for w in warnings[:10]:
            print(w)
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
    
    return True, []


def check_zombie_contract(repo_root: Path) -> tuple[bool, list[str]]:
    """
    Check 3: Zombie classification contract presence check
    
    Ensure AOD has explicit activity evidence fields for deterministic zombie logic.
    """
    issues = []
    found_keywords = set()
    
    src_path = repo_root / "src"
    if not src_path.exists():
        src_path = repo_root
    
    py_files = list(src_path.glob("**/*.py"))
    py_files = [f for f in py_files if ".venv" not in str(f)]
    
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            content_lower = content.lower()
            
            for keyword in ACTIVITY_EVIDENCE_KEYWORDS:
                if keyword.lower() in content_lower:
                    found_keywords.add(keyword)
        except Exception:
            pass
    
    if not found_keywords:
        issues.append("No activity evidence fields found; zombie logic cannot be deterministic")
    else:
        print(f"  Found activity evidence fields: {sorted(found_keywords)}")
    
    return len(issues) == 0, issues


def check_timestamp_integrity(repo_root: Path) -> tuple[bool, list[str]]:
    """
    Check 4: Timestamp integrity guardrail
    
    Inspect local DB for CURRENT_TIMESTAMP defaults.
    """
    warnings = []
    
    db_files = []
    for ext in DB_EXTENSIONS:
        db_files.extend(repo_root.glob(f"**/*{ext}"))
    db_files = [f for f in db_files if ".venv" not in str(f) and "node_modules" not in str(f)]
    
    for db_file in db_files:
        if db_file.stat().st_size == 0:
            continue
            
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"  DB: {db_file.relative_to(repo_root)}")
            print(f"    Tables: {tables}")
            
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                for col in columns:
                    col_name, col_type, _, default_val, _ = col[1], col[2], col[3], col[4], col[5] if len(col) > 5 else None
                    if default_val and "CURRENT_TIMESTAMP" in str(default_val).upper():
                        warnings.append(f"    WARN: {table}.{col_name} has CURRENT_TIMESTAMP default")
            
            conn.close()
        except Exception as e:
            print(f"  Could not inspect {db_file}: {e}")
    
    db_url = "present" if os.environ.get("DATABASE_URL") else "absent"
    supabase = "present" if os.environ.get("SUPABASE_URL") else "absent"
    replit_db = "present" if os.environ.get("REPLIT_DB_URL") else "absent"
    
    print(f"  ENV: DATABASE_URL={db_url}, SUPABASE_URL={supabase}, REPLIT_DB_URL={replit_db}")
    
    for w in warnings:
        print(w)
    
    return True, []


def check_api_smoke(port: int = 5000) -> tuple[bool, list[str]]:
    """
    Check 5: API smoke (optional, secondary)
    
    Quick GET to /health if server is running. Does not start server.
    """
    import socket
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            try:
                import urllib.request
                req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        print(f"  API on port {port}: reachable, /api/health returned 200")
                    else:
                        print(f"  API on port {port}: reachable, /api/health returned {resp.status}")
            except Exception as e:
                print(f"  API on port {port}: reachable but /api/health failed: {e}")
        else:
            print(f"  API on port {port}: not reachable (server not running)")
    except Exception as e:
        print(f"  API check error: {e}")
    
    return True, []


def main():
    try:
        repo_root = find_repo_root()
        print_header(repo_root)
        
        all_passed = True
        all_issues = []
        
        checks = [
            ("STORAGE_MODALITY", check_storage_modality),
            ("DETERMINISTIC_POLICY", check_deterministic_policy),
            ("ZOMBIE_CONTRACT", check_zombie_contract),
            ("TIMESTAMP_INTEGRITY", check_timestamp_integrity),
            ("API_SMOKE", check_api_smoke),
        ]
        
        for check_name, check_fn in checks:
            print(f"CHECK {check_name}:")
            try:
                if check_name == "API_SMOKE":
                    passed, issues = check_fn()
                else:
                    passed, issues = check_fn(repo_root)
                
                if passed:
                    print(f"  RESULT: PASS")
                else:
                    print(f"  RESULT: FAIL")
                    for issue in issues:
                        print(f"    - {issue}")
                    all_passed = False
                    all_issues.extend(issues)
            except Exception as e:
                print(f"  RESULT: ERROR - {e}")
                all_passed = False
            print()
        
        print("=" * 60)
        if all_passed:
            print("OVERALL: PASS")
            sys.exit(0)
        else:
            print("OVERALL: FAIL")
            for issue in all_issues:
                print(f"  - {issue}")
            sys.exit(2)
            
    except Exception as e:
        print(f"ERROR: Script could not run: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
