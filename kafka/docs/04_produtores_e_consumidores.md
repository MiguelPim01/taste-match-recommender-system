# 04 — Produtores e consumidores

## Produtores

Os três produtores Java percorrem um conjunto configurável de usuários e restaurantes. Cada evento recebe UUID e instante UTC novos. O conjunto pequeno e repetido faz com que seja possível observar contagens e substituições nas matrizes rapidamente.

Os produtores usam `acks=all`, cliente idempotente e os três brokers como bootstrap servers. Se uma publicação falhar temporariamente, o processo mantém o container ativo e tenta novamente.

## Consumidores

Cada consumidor possui um grupo independente:

| Tópico | Grupo |
| --- | --- |
| `view-restaurant` | `view-matrix-consumer-v1` |
| `comment-restaurant` | `comment-matrix-consumer-v1` |
| `review-restaurant` | `review-matrix-consumer-v1` |

O commit automático está desabilitado. Para cada mensagem válida, o consumidor grava o evento e atualiza a matriz em uma transação SQLite. O offset é confirmado depois que todo o lote foi persistido.

Se o processo cair entre o commit SQLite e o commit Kafka, a mensagem poderá ser entregue novamente. A chave primária `event_id` transforma a repetição em `DUPLICATE`, sem alterar a matriz pela segunda vez. Uma falha de banco encerra a sessão atual sem confirmar o lote; o consumidor reconecta e o reprocessa.

## Ordem

A chave Kafka é `user_id`, portanto as ações do mesmo usuário permanecem na mesma partição. Para comentários e avaliações, a matriz conserva o evento com maior `occurred_at`; em empate, o maior `event_id`. Essa regra não depende da ordem de chegada entre partições ou após reentregas.
