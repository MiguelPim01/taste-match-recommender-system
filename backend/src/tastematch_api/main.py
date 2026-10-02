"""FastAPI app: seeds the read model, owns the Kafka publisher and runs the projector and the SSE hub."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import partial

import uvicorn
from confluent_kafka import Consumer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tastematch_api.kafka.producer import KafkaPublisher, Publisher
from tastematch_api.kafka.projector import Projector, kafka_consumer
from tastematch_api.realtime.hub import Hub
from tastematch_api.routes import dashboard, health, interactions, me, restaurants, stream, users
from tastematch_api.routes.interactions import ViewThrottle
from tastematch_api.seed import seed_catalog, seed_profiles
from tastematch_api.settings import Settings
from tastematch_api.store import create_db_engine


LOG = logging.getLogger("tastematch-api")


def create_app(settings: Settings | None = None, publisher: Publisher | None = None,
               consumer_factory: Callable[[], Consumer] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings.database_url)
        restaurants_loaded = seed_catalog(engine, settings.sample_dir)
        profiles_loaded = seed_profiles(engine, settings.sample_dir)
        LOG.info("Catálogo com %d restaurantes e %d perfis do Yelp", restaurants_loaded, profiles_loaded)
        hub = Hub(asyncio.get_running_loop())
        projector = Projector(
            engine,
            consumer_factory or partial(kafka_consumer, settings.kafka_bootstrap_servers, settings.projection_group),
            hub.projected,
        )
        projector.start()
        activity = asyncio.create_task(hub.run_activity())
        app.state.settings, app.state.engine, app.state.hub, app.state.projector = settings, engine, hub, projector
        app.state.publisher = publisher or KafkaPublisher(settings.kafka_bootstrap_servers, settings.publish_timeout_s)
        app.state.view_throttle = ViewThrottle(settings.view_dedup_seconds)
        try:
            yield
        finally:
            activity.cancel()
            hub.close()
            projector.stop()
            app.state.publisher.close()
            engine.dispose()

    app = FastAPI(title="TasteMatch API", version="0.4.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    for module in (users, restaurants, interactions, me, stream, dashboard, health):
        app.include_router(module.router)
    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Conexões SSE ficam abertas; sem limite, um restart esperaria cada aba fechar.
    uvicorn.run("tastematch_api.main:create_app", factory=True, host="0.0.0.0", port=8000,
                timeout_graceful_shutdown=5)
