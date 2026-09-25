# 03 — Execução

## Pré-requisito

É necessário apenas Docker com Docker Compose v2. Maven, Java e scripts Kafka são fornecidos pelas imagens durante o build e a execução.

## Subir o ambiente

A partir da raiz do repositório:

```bash
cd kafka
docker compose up --build -d
docker compose ps
```

O primeiro build baixa as imagens e dependências Maven. O serviço `topic-init` termina após criar os tópicos; o estado `Exited (0)` desse serviço é esperado.

Para acompanhar eventos:

```bash
docker compose logs -f view-producer view-matrix-consumer
docker compose logs -f comment-producer comment-matrix-consumer
docker compose logs -f review-producer review-matrix-consumer
```

## Configuração dos dados de demonstração

As variáveis podem ser informadas na execução:

```bash
PRODUCER_INTERVAL_MS=2500 DEMO_USER_COUNT=10 DEMO_RESTAURANT_COUNT=20 \
  docker compose up --build -d
```

Os padrões são intervalo de 1 segundo, cinco usuários e oito restaurantes.

## Encerrar e limpar

`docker compose down` remove containers e rede, preservando volumes Kafka e bancos SQLite. `docker compose down -v` também apaga os volumes internos dos brokers, mas preserva os bancos do bind mount `data/`.

Para começar novamente com tópicos vazios, execute `docker compose down -v`. Caso também queira zerar as matrizes, remova manualmente `data/views.db`, `data/comments.db`, `data/reviews.db` e seus arquivos `-wal`/`-shm` depois que os containers estiverem parados.

## Diagnóstico

```bash
docker compose ps
docker compose logs kafka-1 kafka-2 kafka-3
docker compose logs topic-init
docker compose exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe
```

Se uma porta do host já estiver ocupada, libere `29092`, `39092` ou `49092` antes de subir o ambiente.
