"""Load a three-model bundle and combine source rankings with weighted RRF."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

import torch
from recbole.data.interaction import Interaction
from recbole.utils import get_model

from models.recbole_models import SIGNALS


class Ensemble:
    def __init__(self, bundle_dir: Path):
        self.metadata = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
        self.models = {}
        for signal in SIGNALS:
            saved = torch.load(bundle_dir / f"{signal}.pth", map_location="cpu", weights_only=False)
            config, dataset = saved["config"], saved["dataset"]
            model = get_model("NeuMF")(config, dataset).to("cpu")
            model.load_state_dict(saved["state_dict"])
            model.eval()
            self.models[signal] = (model, dataset)
        self.observed = {tuple(pair) for pair in self.metadata["observed"]}
        self.low_ratings = {tuple(pair) for pair in self.metadata["low_ratings"]}

    def recommend(self, user_id: str, limit: int = 10, candidates: list[str] | None = None) -> list[str]:
        items = candidates if candidates is not None else self.metadata["restaurants"]
        items = [item for item in items if (user_id, item) not in self.observed
                 and (user_id, item) not in self.low_ratings]
        if not items:
            return []
        source_rankings = []
        for signal in SIGNALS:
            model, dataset = self.models[signal]
            user_tokens = dataset.field2token_id[dataset.uid_field]
            item_tokens = dataset.field2token_id[dataset.iid_field]
            user_index = user_tokens.get(user_id)
            known_items = [(item, item_tokens[item]) for item in items if item in item_tokens]
            if user_index is None or not known_items:
                continue
            interaction = Interaction({
                dataset.uid_field: torch.full((len(known_items),), user_index, dtype=torch.long),
                dataset.iid_field: torch.tensor([index for _, index in known_items], dtype=torch.long),
            })
            with torch.no_grad():
                scores = model.predict(interaction).detach().cpu().tolist()
            ranking = [item for (item, _), score in sorted(zip(known_items, scores),
                       key=lambda row: (-row[1], row[0][0]))]
            source_rankings.append((self.metadata["weights"][signal], ranking))
        if not source_rankings:
            popularity = [item for item in self.metadata["popularity"] if item in items]
            return (popularity + sorted(set(items) - set(popularity)))[:limit]
        score_by_item = {item: 0.0 for item in items}
        total_weight = sum(weight for weight, _ in source_rankings)
        for weight, ranking in source_rankings:
            for rank, item in enumerate(ranking, start=1):
                score_by_item[item] += (weight / total_weight) / (60 + rank)
        return sorted(items, key=lambda item: (-score_by_item[item], item))[:limit]


def sampled_candidates(metadata: dict, split: str) -> dict[str, list[str]]:
    observed = {tuple(pair) for pair in metadata["observed"]}
    held_out = {tuple(pair) for part in ("valid", "test") for pair in metadata[part]}
    result = {}
    for user_id, positive in metadata[split]:
        available = [item for item in metadata["restaurants"] if item != positive
                     and (user_id, item) not in observed and (user_id, item) not in held_out]
        if len(available) < 10:
            raise ValueError(f"Menos de 10 negativos para usuário {user_id}")
        seed = int(hashlib.sha256(f"{split}:{user_id}:42".encode()).hexdigest(), 16)
        result[user_id] = [positive] + random.Random(seed).sample(sorted(available), 10)
    return result


def sampled_ndcg(bundle_dir: Path, split: str, *, candidates_by_user: dict | None = None) -> float:
    ensemble = Ensemble(bundle_dir)
    metadata = ensemble.metadata
    scores = []
    selected = candidates_by_user or sampled_candidates(metadata, split)
    for user_id, positive in metadata[split]:
        candidates = selected[user_id]
        ranking = ensemble.recommend(user_id, limit=10, candidates=candidates)
        scores.append(1 / math.log2(ranking.index(positive) + 2) if positive in ranking else 0.0)
    if not scores:
        raise ValueError("Validação sem pares elegíveis")
    return sum(scores) / len(scores)
