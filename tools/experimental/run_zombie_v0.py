#!/usr/bin/env python3
"""
Run the Zombie v0 Standalone server on port 5055.

Usage:
    python tools/experimental/run_zombie_v0.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import uvicorn

if __name__ == "__main__":
    print("Starting Zombie v0 Standalone server on port 5055...")
    uvicorn.run(
        "src.experimental.zombie_v0_standalone.app:app",
        host="0.0.0.0",
        port=5055,
        reload=False
    )
