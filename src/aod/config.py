import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
FARM_URL = os.getenv("FARM_URL", "https://farm.example.com")

# Preview mode is enabled when no database URL is provided. This keeps the app bootable
# on “pretty preview” hosts (e.g., Render) without provisioning Postgres.
PREVIEW_MODE = DATABASE_URL is None
