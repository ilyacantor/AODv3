#!/usr/bin/env python3
"""
Runner script for Zombie v0 Standalone App

Runs on port 5055, completely independent of the main AOD server.
Does not import or depend on any existing AOD modules.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def main():
    import uvicorn
    
    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: No database configured. Set SUPABASE_DB_URL or DATABASE_URL.")
        sys.exit(1)
    
    print("Starting Zombie v0 Standalone App on port 5055...")
    print("Database: configured")
    print("Endpoint: GET /zombies?run_id=...&window_days=...")
    
    uvicorn.run(
        "src.experimental.zombie_v0_standalone.app:app",
        host="0.0.0.0",
        port=5055,
        reload=False
    )


if __name__ == "__main__":
    main()
