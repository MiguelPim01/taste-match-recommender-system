# Taste Match Recommender System

Recomendador de restaurantes baseado no Yelp Open Dataset. O Compose da raiz executa Kafka, consumidores SQLite, carga Yelp, treinamento RecBole e MLflow. Backend e frontend ainda não fazem parte desta etapa.

Com Docker Compose v2.20 ou superior e os arquivos Yelp em `recommender_training/data/yelp/`:

```bash
docker compose up --build -d
docker compose logs -f yelp-sample yelp-seed-replay recommender-worker
docker compose exec recommender-worker taste-match-training status
```

O primeiro treino começa após a carga inicial de 100 usuários e 300 restaurantes. A reprodução posterior alimenta os retreinos. Consulte o [guia de treinamento](recommender_training/README.md) para inspecionar o modelo e [Kafka](kafka/README.md) para a demonstração sintética isolada. O MLflow fica em [http://localhost:5000](http://localhost:5000). Os brokers da raiz expõem `29192`, `39192` e `49192`, preservando as portas da demonstração Kafka isolada.
