"""Train three small implicit-feedback NeuMF models with RecBole."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from recbole.config import Config
from recbole.data import create_dataset, data_preparation
from recbole.utils import get_model, get_trainer, init_seed


SIGNALS = ("ratings", "comments", "views")


def train_models(snapshot_dir: Path, bundle_dir: Path, configuration: Path) -> dict:
    results = {}
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for signal in SIGNALS:
        config = Config(
            model="NeuMF", dataset=signal, config_file_list=[str(configuration)],
            config_dict={
                "data_path": str(snapshot_dir),
                "checkpoint_dir": str(snapshot_dir / signal / "checkpoints"),
                "show_progress": False,
            },
        )
        init_seed(config["seed"], config["reproducibility"])
        dataset = create_dataset(config)
        train_data, valid_data, test_data = data_preparation(config, dataset)
        model = get_model("NeuMF")(config, train_data.dataset).to(config["device"])
        trainer = get_trainer(config["MODEL_TYPE"], "NeuMF")(config, model)
        _, valid_result = trainer.fit(train_data, valid_data, saved=True, show_progress=False)
        test_result = trainer.evaluate(test_data, model_file=trainer.saved_model_file, show_progress=False)
        checkpoint = torch.load(trainer.saved_model_file, map_location="cpu", weights_only=False)
        torch.save({"config": config, "dataset": dataset, "state_dict": checkpoint["state_dict"]},
                   bundle_dir / f"{signal}.pth")
        results[signal] = {
            "valid": {key: float(value) for key, value in valid_result.items()},
            "test": {key: float(value) for key, value in test_result.items()},
            "interactions": int(dataset.inter_num),
        }
    (bundle_dir / "model_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
