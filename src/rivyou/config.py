import os
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get("RIVYOU_WORK_DIR", ROOT / "work")).resolve()
RULE_VERSION = "2026-09-30.8"
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class CrawlConfig:
    operation: str = "collect"
    concurrency: int = 8
    delay_seconds: float = 2.0
    timeout_seconds: float = 20.0
    max_pages: int = 7
    max_bytes: int = 8 * 1024 * 1024
    max_redirects: int = 5
    retries: int = 2
    user_agent: str = "RivyouResearch/0.1"
    freshness_days: int = 7
    offline: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
