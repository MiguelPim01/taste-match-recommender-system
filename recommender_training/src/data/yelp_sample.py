"""Build a small, reproducible Yelp subgraph for the local demonstration."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


BUSINESS_FILE = "yelp_academic_dataset_business.json"
REVIEW_FILE = "yelp_academic_dataset_review.json"
CATALOG_FILE = "catalog.json"
SEED = 42
SAMPLE_VERSION = 2
RESTAURANT_COUNT = 300
USER_COUNT = 100


def _rows(path: Path):
    with path.open(encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def _source_signature(yelp_dir: Path) -> dict:
    return {
        name: {"size": (yelp_dir / name).stat().st_size, "mtime_ns": (yelp_dir / name).stat().st_mtime_ns}
        for name in (BUSINESS_FILE, REVIEW_FILE)
    }


def prepare(yelp_dir: Path, output_dir: Path) -> dict:
    """Select 100 eligible users, then 300 restaurants they actually reviewed."""
    signature = _source_signature(yelp_dir)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists() and all((output_dir / f).exists() for f in ("seed.jsonl", "live.jsonl")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_signature") == signature and manifest.get("sample_version") == SAMPLE_VERSION:
            if not (output_dir / CATALOG_FILE).exists():
                _write_catalog(yelp_dir, output_dir, set(manifest["restaurants"]))
            return manifest

    restaurants = []
    for business in _rows(yelp_dir / BUSINESS_FILE):
        categories = {part.strip() for part in (business.get("categories") or "").split(",")}
        if (business.get("is_open") == 1 and business.get("city") == "Philadelphia"
                and business.get("state") == "PA" and "Restaurants" in categories):
            restaurants.append((business["review_count"], business["business_id"]))
    restaurants.sort(key=lambda row: (-row[0], row[1]))
    if len(restaurants) < RESTAURANT_COUNT:
        raise ValueError("Yelp não contém 300 restaurantes abertos em Filadélfia")
    initial = {business_id for _, business_id in restaurants[:RESTAURANT_COUNT]}
    city_ids = {business_id for _, business_id in restaurants}

    user_restaurants: dict[str, set[str]] = defaultdict(set)
    user_positives: Counter[str] = Counter()
    for review in _rows(yelp_dir / REVIEW_FILE):
        if review["business_id"] in initial:
            user_restaurants[review["user_id"]].add(review["business_id"])
            if review["stars"] >= 4:
                user_positives[review["user_id"]] += 1
    eligible = sorted(user_id for user_id, ids in user_restaurants.items()
                      if len(ids) >= 10 and user_positives[user_id] >= 5)
    if len(eligible) < USER_COUNT:
        raise ValueError(f"Apenas {len(eligible)} usuários têm 10 restaurantes e 5 reviews positivos")
    selected_users = set(random.Random(SEED).sample(eligible, USER_COUNT))

    # A second streaming pass retains full text only for the selected users.
    reviews: dict[str, list[dict]] = defaultdict(list)
    outside_counts: Counter[str] = Counter()
    for review in _rows(yelp_dir / REVIEW_FILE):
        if review["user_id"] not in selected_users or review["business_id"] not in city_ids:
            continue
        if review["business_id"] in initial:
            reviews[review["user_id"]].append(review)
        else:
            outside_counts[review["business_id"]] += 1
            reviews[review["user_id"]].append(review)

    covered = {review["business_id"] for user_reviews in reviews.values()
               for review in user_reviews if review["business_id"] in initial}
    missing = RESTAURANT_COUNT - len(covered)
    replacements = sorted(outside_counts, key=lambda business_id: (-outside_counts[business_id], business_id))[:missing]
    if len(replacements) != missing:
        raise ValueError("Os usuários selecionados não cobrem 300 restaurantes")
    selected_restaurants = covered | set(replacements)
    reviews = {user_id: [review for review in user_reviews
                         if review["business_id"] in selected_restaurants]
               for user_id, user_reviews in reviews.items()}

    remaining_per_item = Counter(review["business_id"] for user_reviews in reviews.values()
                                 for review in user_reviews)
    held_out: dict[str, list[dict]] = {"valid": [], "test": []}
    training_reviews: dict[str, list[dict]] = {}
    for user_id in sorted(selected_users):
        ordered = sorted(reviews[user_id], key=lambda review: (review["date"], review["review_id"]))
        candidates = [review for review in reversed(ordered) if review["stars"] >= 4]
        selected = []
        selected_items = set()
        user_item_counts = Counter(review["business_id"] for review in ordered)
        for review in candidates:
            item = review["business_id"]
            if item not in selected_items and remaining_per_item[item] > user_item_counts[item]:
                selected.append(review)
                selected_items.add(item)
                remaining_per_item[item] -= user_item_counts[item]
                if len(selected) == 2:
                    break
        if len(selected) != 2:
            raise ValueError(f"Usuário {user_id} não permite validação e teste sem perder cobertura")
        held_out["test"].append(selected[0])
        held_out["valid"].append(selected[1])
        training_reviews[user_id] = [review for review in ordered if review["business_id"] not in selected_items]
        if len({review["business_id"] for review in training_reviews[user_id]}) < 8:
            raise ValueError(f"Histórico de treino insuficiente para {user_id}")

    seed_reviews, live_reviews = [], []
    seed_item_counts = Counter(review["business_id"] for user_reviews in training_reviews.values()
                               for review in user_reviews)
    for user_id in sorted(selected_users):
        ordered = training_reviews[user_id]
        live_count = max(1, math.ceil(len(ordered) * 0.10))
        selected_live = set()
        for review in reversed(ordered):
            if seed_item_counts[review["business_id"]] > 1:
                selected_live.add(review["review_id"])
                seed_item_counts[review["business_id"]] -= 1
                if len(selected_live) == live_count:
                    break
        if len(selected_live) != live_count:
            raise ValueError(f"Não há reviews posteriores suficientes sem perder o restaurante de {user_id}")
        seed_reviews.extend(review for review in ordered if review["review_id"] not in selected_live)
        live_reviews.extend(review for review in ordered if review["review_id"] in selected_live)
    seed_reviews.sort(key=lambda review: (review["date"], review["review_id"]))
    live_reviews.sort(key=lambda review: (review["date"], review["review_id"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, source in (("seed", seed_reviews), ("live", live_reviews)):
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as destination:
            for review in source:
                for event in _events(review):
                    destination.write(json.dumps(event, ensure_ascii=False) + "\n")
    manifest = {
        "sample_version": SAMPLE_VERSION,
        "source_signature": signature,
        "selection_seed": SEED,
        "eligible_users": len(eligible),
        "users": sorted(selected_users),
        "restaurants": sorted(selected_restaurants),
        "seed_reviews": len(seed_reviews),
        "live_reviews": len(live_reviews),
        "valid": [_pair(review) for review in held_out["valid"]],
        "test": [_pair(review) for review in held_out["test"]],
    }
    _write_catalog(yelp_dir, output_dir, selected_restaurants)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _write_catalog(yelp_dir: Path, output_dir: Path, restaurant_ids: set[str]) -> None:
    """Keep the display fields of the sampled restaurants for the backend; the manifest only has their IDs."""
    catalog = []
    for business in _rows(yelp_dir / BUSINESS_FILE):
        if business["business_id"] in restaurant_ids:
            catalog.append({
                "id": business["business_id"],
                "name": business["name"],
                "address": business.get("address") or None,
                "city": business.get("city"),
                "state": business.get("state"),
                "postal_code": business.get("postal_code") or None,
                "latitude": business.get("latitude"),
                "longitude": business.get("longitude"),
                "stars": business.get("stars"),
                "review_count": business.get("review_count", 0),
                "categories": [part.strip() for part in (business.get("categories") or "").split(",") if part.strip()],
            })
    if len(catalog) != len(restaurant_ids):
        raise ValueError(f"Catálogo incompleto: {len(catalog)} de {len(restaurant_ids)} restaurantes")
    catalog.sort(key=lambda row: row["id"])
    (output_dir / CATALOG_FILE).write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def _pair(review: dict) -> dict:
    return {"user_id": review["user_id"], "restaurant_id": review["business_id"], "review_id": review["review_id"]}


def _events(review: dict):
    common = {
        "schema_version": 1,
        "user_id": review["user_id"],
        "restaurant_id": review["business_id"],
    }
    timestamp = datetime.strptime(review["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    review_id = review["review_id"]
    view_count = 1 + int(hashlib.sha256(review_id.encode()).hexdigest(), 16) % 3
    for index in range(view_count):
        yield {**common, "event_id": f"view:{review_id}:{index}", "type": "restaurant.viewed",
               "occurred_at": (timestamp - timedelta(seconds=view_count - index)).isoformat().replace("+00:00", "Z")}
    yield {**common, "event_id": f"review:{review_id}:rated", "type": "restaurant.rated",
           "occurred_at": timestamp.isoformat().replace("+00:00", "Z"), "stars": int(review["stars"])}
    text = review.get("text", "").strip()
    if text:
        yield {**common, "event_id": f"review:{review_id}:commented", "type": "restaurant.commented",
               "occurred_at": timestamp.isoformat().replace("+00:00", "Z"), "text": text}
