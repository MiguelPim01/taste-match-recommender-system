# Taste Match Recommender System

Recomendador de restaurantes baseado no Yelp Open Dataset. O Compose da raiz executa Kafka, consumidores SQLite, carga Yelp, treinamento RecBole e MLflow. Backend e frontend ainda não fazem parte desta etapa.

Requer Docker Compose v2.20 ou superior. Baixe o [Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/), extraia o arquivo e copie `yelp_academic_dataset_business.json` e `yelp_academic_dataset_review.json` para `recommender_training/data/yelp/`. Sem eles, `yelp-sample` termina com `FileNotFoundError` e a carga e o treino não começam.

```bash
mkdir -p recommender_training/data/yelp
cp /caminho/para/yelp_academic_dataset_business.json \
   /caminho/para/yelp_academic_dataset_review.json \
   recommender_training/data/yelp/
```

Se o Compose já tiver sido executado sem os arquivos, o Docker terá criado o diretório como root e o `cp` falhará por permissão. Nesse caso, rode antes `sudo chown -R $USER:$USER recommender_training/data`.

Depois suba o ambiente:

```bash
docker compose up --build -d
docker compose logs -f yelp-sample yelp-seed-replay recommender-worker
docker compose exec recommender-worker taste-match-training status
```

O primeiro treino começa após a carga inicial de 100 usuários e 300 restaurantes. A reprodução posterior alimenta os retreinos. Consulte o [guia de treinamento](recommender_training/README.md) para inspecionar o modelo e [Kafka](kafka/README.md) para a demonstração sintética isolada. O MLflow fica em [http://localhost:5000](http://localhost:5000). O [Kafka UI](https://github.com/kafbat/kafka-ui) fica em [http://localhost:8085](http://localhost:8085) e mostra brokers, tópicos, mensagens e consumer groups; a porta muda com `KAFKA_UI_PORT`. Os brokers da raiz expõem `29192`, `39192` e `49192`, preservando as portas da demonstração Kafka isolada.
