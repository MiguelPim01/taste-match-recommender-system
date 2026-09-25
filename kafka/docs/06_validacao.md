# 06 — Roteiro de validação

## Cluster e tópicos

```bash
docker compose up --build -d
docker compose ps
docker compose exec kafka-1 /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka-1:19092 --describe
```

O resultado deve listar `view-restaurant`, `comment-restaurant` e `review-restaurant`, cada um com três partições, três réplicas por partição e duas réplicas sincronizadas mínimas.

## Fluxo completo

Aguarde alguns segundos e confira:

```bash
docker compose logs --tail=20 view-producer comment-producer review-producer
docker compose logs --tail=20 view-matrix-consumer comment-matrix-consumer review-matrix-consumer
```

Os produtores devem registrar `Evento publicado`; os consumidores, `outcome=ACCEPTED`. Consulte as matrizes usando os comandos de `05_matrizes_sqlite.md`.

## Reinício e persistência

```bash
docker compose restart view-matrix-consumer
docker compose down
docker compose up -d
```

As contagens e eventos anteriores devem continuar nos bancos. Mensagens reentregues aparecem como `outcome=DUPLICATE` e não incrementam novamente a matriz.

## Continuidade com um broker parado

```bash
docker compose stop kafka-3
docker compose logs -f --tail=10 view-producer view-matrix-consumer
```

Com dois brokers ativos, novas publicações e consumos devem continuar. Restaure o nó com `docker compose start kafka-3`.

## Testes Java

Os testes unitários são executados no build Docker. Também podem ser executados em uma máquina com Maven e Java 21:

```bash
mvn test
```

Eles verificam contratos, compatibilidade com campos novos, rejeições, deduplicação e seleção temporal dos valores das matrizes.
