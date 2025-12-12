import asyncio
import os
from pathlib import Path
from src.aod.db import init_db, close_db, execute, fetchval


MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


async def get_current_version() -> int:
    try:
        version = await fetchval("SELECT MAX(version) FROM schema_version")
        return version or 0
    except Exception:
        return 0


async def run_migrations():
    await init_db()
    
    current_version = await get_current_version()
    print(f"Current schema version: {current_version}")
    
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    
    for migration_file in migration_files:
        version = int(migration_file.name.split("_")[0])
        
        if version > current_version:
            print(f"Applying migration {migration_file.name}...")
            sql = migration_file.read_text()
            
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for statement in statements:
                if statement:
                    await execute(statement)
            
            print(f"Migration {version} applied successfully")
    
    await close_db()
    print("Migrations complete!")


if __name__ == "__main__":
    asyncio.run(run_migrations())
