"""Central settings. `settings` is a plain object so tests can override fields."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")  # must run before langchain reads LANGSMITH_* / OPENAI_*

# Narrowest scope that can read, label, archive, trash and create drafts.
# It cannot permanently delete. (It *can* send, which is why no send tool exists in code.)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass
class Settings:
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_temperature: str = os.getenv("OPENAI_TEMPERATURE", "0")

    # Stop rule. Enforced inside the graph, not in the prompt.
    max_steps: int = _int("MAX_STEPS", 15)        # LLM calls per run
    max_writes: int = _int("MAX_WRITES", 15)      # executed writes per run
    max_tokens: int = _int("MAX_TOKENS", 60000)   # total tokens per run

    api_token: str = os.getenv("API_TOKEN", "")

    credentials_path: Path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", BASE_DIR / "credentials.json"))
    token_path: Path = Path(os.getenv("GOOGLE_TOKEN_PATH", BASE_DIR / "token.json"))
    log_dir: Path = BASE_DIR / "logs"

    price_in_per_1m: float = float(os.getenv("PRICE_IN_PER_1M", "0.40"))
    price_out_per_1m: float = float(os.getenv("PRICE_OUT_PER_1M", "1.60"))


settings = Settings()
