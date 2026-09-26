"""Read stable snapshots of the Kafka consumers' three SQLite matrices."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


DATABASES = {"views": "views.db", "comments": "comments.db", "reviews": "reviews.db"}
WEIGHTS = {"ratings": 0.5, "comments": 0.3, "views": 0.2}


def counts(database_dir: Path) -> dict[str, int]:
    result = {}
    for signal, filename in DATABASES.items():
        path = database_dir / filename
        if not path.exists():
            return {}
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) as connection:
            result[signal] = connection.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
    return result


def create_snapshot(database_dir: Path, output_dir: Path, manifest_path: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = {}
    for signal, filename in DATABASES.items():
        source_path = database_dir / filename
        destination_path = output_dir / filename
        with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=30) as source:
            with sqlite3.connect(destination_path) as destination:
                source.backup(destination)
        copied[signal] = destination_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    users = set(manifest["users"])
    restaurants = set(manifest["restaurants"])
    held_out = {(row["user_id"], row["restaurant_id"]) for split in ("valid", "test")
                for row in manifest[split]}
    matrices = {}
    snapshot_counts = {}
    queries = {
        "views": "SELECT user_id, restaurant_id, view_count FROM view_matrix",
        "comments": "SELECT user_id, restaurant_id, comment_text FROM comment_matrix",
        "reviews": "SELECT user_id, restaurant_id, stars FROM review_matrix",
    }
    for signal, path in copied.items():
        with sqlite3.connect(path) as connection:
            snapshot_counts[signal] = connection.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
            matrices[signal] = {(uid, item): value for uid, item, value in connection.execute(queries[signal])
                                if uid in users and item in restaurants and (uid, item) not in held_out}

    analyzer = SentimentIntensityAnalyzer()
    positives = {
        "ratings": {pair for pair, stars in matrices["reviews"].items() if stars >= 4},
        "comments": {pair for pair, comment in matrices["comments"].items()
                     if analyzer.polarity_scores(comment)["compound"] >= 0.05},
        "views": set(matrices["views"]),
    }
    observed = set().union(*(set(rows) for rows in matrices.values()))
    low_ratings = {pair for pair, stars in matrices["reviews"].items() if stars <= 2}
    popularity = Counter(item for _, item in positives["ratings"])
    valid = [(row["user_id"], row["restaurant_id"]) for row in manifest["valid"]]
    test = [(row["user_id"], row["restaurant_id"]) for row in manifest["test"]]

    for signal, pairs in positives.items():
        folder = output_dir / signal
        folder.mkdir(exist_ok=True)
        _atomic(folder / f"{signal}.train.inter", sorted(pairs))
        _atomic(folder / f"{signal}.valid.inter", valid)
        _atomic(folder / f"{signal}.test.inter", test)
        (folder / f"{signal}.user").write_text("user_id:token\n" + "\n".join(sorted(users)) + "\n", encoding="utf-8")
        (folder / f"{signal}.item").write_text("item_id:token\n" + "\n".join(sorted(restaurants)) + "\n", encoding="utf-8")

    metadata = {
        "counts": snapshot_counts,
        "positive_counts": {signal: len(pairs) for signal, pairs in positives.items()},
        "users": sorted(users), "restaurants": sorted(restaurants),
        "observed": sorted([list(pair) for pair in observed]),
        "low_ratings": sorted([list(pair) for pair in low_ratings]),
        "popularity": [item for item, _ in sorted(popularity.items(), key=lambda row: (-row[1], row[0]))],
        "valid": valid, "test": test, "weights": WEIGHTS,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


def _atomic(path: Path, pairs) -> None:
    with path.open("w", encoding="utf-8") as target:
        target.write("user_id:token\titem_id:token\n")
        for user, item in pairs:
            target.write(f"{user}\t{item}\n")
