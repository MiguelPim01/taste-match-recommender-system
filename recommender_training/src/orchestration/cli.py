"""Local Yelp bootstrap, Kafka retraining worker, and recommendation CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from confluent_kafka import Consumer

from data.snapshot import counts, create_snapshot
from data.yelp_sample import prepare
from messaging.kafka import REQUEST_TOPIC, READY_TOPIC, bootstrap_servers, producer, publish, replay
from models.ranking import Ensemble, sampled_candidates, sampled_ndcg
from models.recbole_models import train_models
from orchestration.state import State


LOG = logging.getLogger("taste-match-training")
ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.getenv("TRAINING_RUNTIME_DIR", ROOT / "runtime"))
MATRICES = Path(os.getenv("MATRIX_DIR", ROOT.parent / "kafka" / "data" / "yelp"))
YELP = Path(os.getenv("YELP_DIR", ROOT / "data" / "yelp"))
CONFIG = ROOT / "config" / "recbole.yaml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state() -> State:
    return State(RUNTIME / "state.db")


def _tracking() -> None:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("restaurant-ensemble")


def _bundle(run_id: str) -> Path:
    return Path(mlflow.artifacts.download_artifacts(artifact_uri=f"runs:/{run_id}/bundle"))


def train_once(state: State, event_id: str, force: bool = False) -> dict | None:
    manifest_path = RUNTIME / "sample" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("A amostra Yelp ainda não foi preparada")
    current = counts(MATRICES)
    previous = state.get("last_counts", {})
    if state.get("champion") and current == previous and not force:
        LOG.info("Sem eventos novos; ignorando %s", event_id)
        state.set("pending_request", None)
        return None
    if not current or any(value == 0 for value in current.values()):
        raise RuntimeError("Matrizes Kafka ainda não contêm as três fontes")

    _tracking()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="training-", dir=RUNTIME) as temporary:
        base = Path(temporary)
        snapshot = base / "snapshot"
        bundle = base / "bundle"
        metadata = create_snapshot(MATRICES, snapshot, manifest_path)
        if any(value < 20 for value in metadata["positive_counts"].values()):
            raise RuntimeError(f"Interações positivas insuficientes: {metadata['positive_counts']}")
        bundle.mkdir()
        (bundle / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        with mlflow.start_run(run_name=f"snapshot-{sum(metadata['counts'].values())}") as run:
            mlflow.set_tag("request_event_id", event_id)
            mlflow.log_params({"users": len(metadata["users"]), "restaurants": len(metadata["restaurants"]),
                               "negative_sampling": "uni10", "model": "NeuMF"})
            model_metrics = train_models(snapshot, bundle, CONFIG)
            candidate_set = sampled_candidates(metadata, "valid")
            candidate_score = sampled_ndcg(bundle, "valid", candidates_by_user=candidate_set)
            test_score = sampled_ndcg(bundle, "test")
            mlflow.log_metric("ensemble_valid_ndcg_at_10", candidate_score)
            mlflow.log_metric("ensemble_test_ndcg_at_10", test_score)
            for signal, result in model_metrics.items():
                mlflow.log_metric(f"{signal}_valid_ndcg_at_10", result["valid"].get("ndcg@10", 0.0))
                mlflow.log_metric(f"{signal}_test_ndcg_at_10", result["test"].get("ndcg@10", 0.0))
                mlflow.log_metric(f"{signal}_positive_count", metadata["positive_counts"][signal])
            mlflow.log_artifacts(str(bundle), artifact_path="bundle")
            candidate_run = run.info.run_id

        champion = state.get("champion")
        champion_score = float("-inf")
        if champion:
            champion_score = sampled_ndcg(_bundle(champion["run_id"]), "valid", candidates_by_user=candidate_set)
        if champion is None or candidate_score > champion_score:
            selected = {"run_id": candidate_run, "metric": candidate_score,
                        "bundle_uri": f"runs:/{candidate_run}/bundle", "counts": metadata["counts"]}
            ready = {"schema_version": 1, "event_id": f"model_ready:{candidate_run}",
                     "type": "model.ready", "run_id": candidate_run,
                     "bundle_uri": selected["bundle_uri"], "metric_name": "NDCG@10",
                     "metric_value": candidate_score, "trained_until_counts": metadata["counts"],
                     "created_at": _now()}
            state.complete(metadata["counts"], champion=selected, ready_event=ready)
            LOG.info("Novo modelo promovido: %s, NDCG@10=%.4f", candidate_run, candidate_score)
            return selected
        state.complete(metadata["counts"])
        LOG.info("Candidato %s não melhorou %.4f <= %.4f", candidate_run, candidate_score, champion_score)
        return None


def _drain_ready(state: State) -> None:
    client = producer()
    for event_id, raw in state.pending_ready():
        publish(client, READY_TOPIC, "ensemble", json.loads(raw))
        state.mark_ready_sent(event_id)


def worker() -> None:
    while True:
        state = _state()
        client = Consumer({"bootstrap.servers": bootstrap_servers(), "group.id": "recommender-training-v1",
                           "enable.auto.commit": False, "auto.offset.reset": "earliest",
                           "max.poll.interval.ms": 1800000})
        try:
            client.subscribe([REQUEST_TOPIC])
            while True:
                _drain_ready(state)
                message = client.poll(2)
                if message is None:
                    continue
                if message.error():
                    raise RuntimeError(str(message.error()))
                event = json.loads(message.value())
                if event.get("type") != "recommender.retrain.requested" or event.get("schema_version") != 1:
                    LOG.warning("Pedido inválido descartado: %s", event)
                    client.commit(message=message, asynchronous=False)
                    continue
                train_once(state, event["event_id"], bool(event.get("force", False)))
                client.commit(message=message, asynchronous=False)
                _drain_ready(state)
        except Exception:
            LOG.exception("Falha no trabalhador; repetindo mensagem após reconexão")
            time.sleep(10)
        finally:
            client.close()
            state.close()


def monitor() -> None:
    threshold = int(os.getenv("RETRAIN_MIN_EVENTS", "300"))
    while True:
        try:
            if not (RUNTIME / "seed.complete").exists():
                time.sleep(5)
                continue
            state = _state()
            try:
                current = counts(MATRICES)
                last = state.get("last_counts", {name: 0 for name in current})
                delta = sum(max(0, current[name] - last.get(name, 0)) for name in current)
                due = bool(current) and (state.get("champion") is None or delta >= threshold)
                if due:
                    fingerprint = ":".join(f"{key}={current[key]}" for key in sorted(current))
                    event_id = "retrain:" + hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
                    pending = state.get("pending_request")
                    if not pending or time.time() - pending.get("sent_at", 0) > 60:
                        event = {"schema_version": 1, "event_id": event_id,
                                 "type": "recommender.retrain.requested", "requested_at": _now(),
                                 "source": "sqlite-monitor", "observed_counts": current}
                        state.set("pending_request", {"event_id": event_id, "sent_at": time.time()})
                        publish(producer(), REQUEST_TOPIC, "ensemble", event)
                        LOG.info("Pedido de treino publicado: %s (%d eventos novos)", event_id, delta)
            finally:
                state.close()
        except Exception:
            LOG.exception("Monitor falhou; nova verificação em breve")
        time.sleep(10)


def _wait_for_seed(count_by_topic: dict[str, int]) -> None:
    expected = {"views": count_by_topic["view-restaurant"],
                "comments": count_by_topic["comment-restaurant"],
                "reviews": count_by_topic["review-restaurant"]}
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        actual = counts(MATRICES)
        if actual and all(actual[signal] >= required for signal, required in expected.items()):
            (RUNTIME / "seed.complete").write_text(json.dumps(expected), encoding="utf-8")
            return
        time.sleep(3)
    raise TimeoutError(f"Consumidores não finalizaram carga: esperado={expected}, atual={counts(MATRICES)}")


def _wait_for_champion() -> None:
    while True:
        state = _state()
        champion = state.get("champion")
        state.close()
        if champion:
            return
        time.sleep(5)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("prepare-yelp")
    replay_command = subcommands.add_parser("replay")
    replay_command.add_argument("split", choices=("seed", "live"))
    subcommands.add_parser("monitor")
    subcommands.add_parser("worker")
    subcommands.add_parser("status")
    subcommands.add_parser("sample-user")
    request_command = subcommands.add_parser("request-train")
    request_command.add_argument("--force", action="store_true")
    train_command = subcommands.add_parser("train")
    train_command.add_argument("--force", action="store_true")
    recommend_command = subcommands.add_parser("recommend")
    recommend_command.add_argument("user_id", nargs="?")
    recommend_command.add_argument("--user-id", dest="user_id_option")
    recommend_command.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.command == "prepare-yelp":
        sample = prepare(YELP, RUNTIME / "sample")
        LOG.info("Amostra pronta: %d usuários, %d restaurantes, %d reviews iniciais, %d posteriores",
                 len(sample["users"]), len(sample["restaurants"]), sample["seed_reviews"], sample["live_reviews"])
    elif args.command == "replay":
        if args.split == "live":
            _wait_for_champion()
        result = replay(RUNTIME / "sample" / f"{args.split}.jsonl",
                        int(os.getenv("LIVE_REPLAY_INTERVAL_MS", "200")) if args.split == "live" else 0)
        LOG.info("Eventos publicados: %s", result)
        if args.split == "seed":
            _wait_for_seed(result)
    elif args.command == "monitor":
        monitor()
    elif args.command == "worker":
        worker()
    elif args.command == "train":
        state = _state()
        try:
            train_once(state, f"manual:{_now()}", args.force)
            _drain_ready(state)
        finally:
            state.close()
    elif args.command == "recommend":
        user_id = args.user_id_option or args.user_id
        if not user_id:
            parser.error("Informe o ID com --user-id (IDs Yelp podem começar com '-')")
        state = _state()
        champion = state.get("champion")
        state.close()
        if not champion:
            parser.error("Nenhum modelo foi promovido ainda")
        _tracking()
        ranking = Ensemble(_bundle(champion["run_id"])).recommend(user_id, args.limit)
        print(json.dumps({"user_id": user_id, "run_id": champion["run_id"], "restaurants": ranking}))
    elif args.command == "status":
        state = _state()
        result = {"champion": state.get("champion"), "last_counts": state.get("last_counts"),
                  "current_counts": counts(MATRICES), "pending_request": state.get("pending_request")}
        state.close()
        print(json.dumps(result, indent=2))
    elif args.command == "sample-user":
        manifest = json.loads((RUNTIME / "sample" / "manifest.json").read_text(encoding="utf-8"))
        print(manifest["users"][0])
    elif args.command == "request-train":
        event = {"schema_version": 1, "event_id": f"manual:{_now()}",
                 "type": "recommender.retrain.requested", "requested_at": _now(),
                 "source": "cli", "force": args.force}
        publish(producer(), REQUEST_TOPIC, "ensemble", event)
        LOG.info("Pedido manual publicado em %s", REQUEST_TOPIC)


if __name__ == "__main__":
    main()
