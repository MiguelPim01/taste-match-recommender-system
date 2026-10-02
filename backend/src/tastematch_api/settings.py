"""Runtime configuration read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str
    database_url: str
    sample_dir: Path
    publish_timeout_s: float
    view_dedup_seconds: int
    cors_origins: tuple[str, ...]
    # Trocar o grupo (v2, v3...) reconstrói a projeção relendo os tópicos desde o início.
    projection_group: str = "backend-projections-v1"
    # O mesmo limite do monitor e do worker; o painel mostra quanto falta para o próximo treino.
    retrain_min_events: int = 300

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29192,localhost:39192,localhost:49192"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./backend.db"),
            sample_dir=Path(os.getenv("SAMPLE_DIR", "../recommender_training/runtime/sample")),
            publish_timeout_s=float(os.getenv("PUBLISH_TIMEOUT_SECONDS", "15")),
            view_dedup_seconds=int(os.getenv("VIEW_DEDUP_SECONDS", "1800")),
            cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
            projection_group=os.getenv("PROJECTION_GROUP", "backend-projections-v1"),
            retrain_min_events=int(os.getenv("RETRAIN_MIN_EVENTS", "300")),
        )
