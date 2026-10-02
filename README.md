# Taste Match Recommender System

Recomendador de restaurantes de Filadélfia baseado no Yelp Open Dataset, construído como um sistema orientado a eventos sobre Apache Kafka. Um único `docker compose` na raiz sobe tudo: Kafka com três brokers, consumidores Java que mantêm as matrizes em SQLite, carga do Yelp, treino com RecBole e MLflow, publicador de recomendações, backend FastAPI e frontend React.

## Antes da primeira vez

Requer Docker Compose v2.20 ou superior. Baixe o [Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/), extraia o arquivo e copie `yelp_academic_dataset_business.json` e `yelp_academic_dataset_review.json` para `recommender_training/data/yelp/`. Sem eles, `yelp-sample` termina com `FileNotFoundError` e a carga e o treino não começam.

```bash
mkdir -p recommender_training/data/yelp
cp /caminho/para/yelp_academic_dataset_business.json \
   /caminho/para/yelp_academic_dataset_review.json \
   recommender_training/data/yelp/
```

Se o Compose já tiver sido executado sem os arquivos, o Docker terá criado o diretório como root e o `cp` falhará por permissão. Nesse caso, rode antes `sudo chown -R $USER:$USER recommender_training/data`.

## Subir tudo

```bash
docker compose up --build -d
```

| Endereço | O que é |
| --- | --- |
| [http://localhost:3000](http://localhost:3000) | App TasteMatch e painel do ciclo de treino |
| [http://localhost:8000/docs](http://localhost:8000/docs) | API do backend |
| [http://localhost:8085](http://localhost:8085) | Kafka UI: brokers, tópicos, mensagens e consumer groups |
| [http://localhost:5000](http://localhost:5000) | MLflow: métricas e pacotes de cada modelo |

O primeiro treino começa depois da carga inicial de 100 usuários e 300 restaurantes; a reprodução posterior do Yelp alimenta os retreinos, um a cada 300 eventos novos. Para acompanhar a carga e o treino:

```bash
docker compose logs -f yelp-sample yelp-seed-replay recommender-worker
docker compose exec recommender-worker taste-match-training status
```

Portas e o diretório das matrizes vêm do `compose.env`, versionado, então não é preciso criar `.env`. Os brokers da raiz expõem `29192`, `39192` e `49192`, preservando as portas da demonstração Kafka isolada; `FRONTEND_PORT`, `BACKEND_PORT`, `KAFKA_UI_PORT` e `RETRAIN_MIN_EVENTS` podem ser trocados por variável de ambiente. `docker compose down` para tudo e preserva os volumes.

## Componentes

- [Kafka](kafka/README.md): brokers, tópicos e consumidores Java; inclui a demonstração sintética isolada.
- [Treinamento](recommender_training/README.md): amostra do Yelp, monitor, worker, publicador de recomendações e MLflow.
- [Backend](backend/README.md): API FastAPI, projeção dos tópicos, tempo real com SSE e a arquitetura do sistema.
- [Frontend](frontend/README.md): app React + Vite servido por nginx.
