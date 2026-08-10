import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
# .env do próprio jokenpo/ (hardware do Thoth + chaves da Anthropic num só lugar).
load_dotenv(BASE_DIR / ".env", override=True)

# -- API keys e modelos por provider --------------------------------
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_ROUTER_MODEL = os.getenv("ANTHROPIC_ROUTER_MODEL", "claude-haiku-4-5-20251001")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# -- Paths ----------------------------------------------------------
LANCEDB_URI = str(BASE_DIR / "tmp" / "lancedb")
SQLITE_DB_FILE = str(BASE_DIR / "agno.db")
