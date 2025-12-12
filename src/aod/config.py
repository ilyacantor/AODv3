import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
FARM_URL = os.getenv("FARM_URL", "https://farm.example.com")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL or SUPABASE_DB_URL must be set")
