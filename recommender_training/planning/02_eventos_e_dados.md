# 02 — Eventos e dados

## Recorte Yelp

`src/data/yelp_sample.py` lê `business.json` e `review.json` linha a linha. Seleciona inicialmente os 300 restaurantes abertos de Filadélfia com maior `review_count`. Entre usuários com reviews de ao menos 10 desses restaurantes e 5 avaliações de 4 ou 5 estrelas, sorteia 100 com semente 42. Se algum restaurante inicial não foi avaliado pelos sorteados, substitui-o por outro restaurante aberto da cidade que eles avaliaram, priorizando o mais frequente. IDs originais são preservados.

Cada usuário contribui com um review positivo para validação e outro para teste. Todos os reviews dos dois pares usuário–restaurante reservados ficam fora do Kafka, inclusive quando o Yelp contém mais de um review do mesmo par. Dos demais reviews, cerca de 10% por usuário são reservados para replay posterior, mantendo pelo menos um review inicial por restaurante. O restante forma a carga inicial. O manifesto registra IDs, divisões e contagens; o cache exige os mesmos arquivos de origem e a mesma versão do algoritmo de amostragem.

Cada review publicado gera uma avaliação, um comentário não vazio e de uma a três visualizações simuladas. A quantidade de visualizações deriva de SHA-256 do `review_id`; os `event_id` são estáveis. Cada evento é JSON UTF-8 com `schema_version: 1`, `event_id`, `type`, `user_id`, `restaurant_id` e `occurred_at` UTC. A chave Kafka é `user_id`. `stars` é inteiro de 1 a 5; comentários trazem `text`.

## Bancos de entrada

Os consumidores Java escrevem `view_matrix(user_id, restaurant_id, view_count)`, `comment_matrix(..., comment_text)` e `review_matrix(..., stars)` nos bancos `views.db`, `comments.db` e `reviews.db`. Cada banco contém `processed_events` para deduplicação. O treinamento usa a API de backup SQLite para obter um retrato estável por banco e registra a contagem de eventos aceitos por fonte. Não existe sequência global entre os três bancos.

## Tópicos de treinamento

Pedido: `recommender-retrain`, chave `ensemble`:

```json
{"schema_version":1,"event_id":"retrain:<id>","type":"recommender.retrain.requested","requested_at":"2026-09-26T12:00:00Z","source":"sqlite-monitor","observed_counts":{"views":100,"comments":100,"reviews":100}}
```

O campo opcional `force: true` permite repetir um treino manual sem dados novos. O treinador usa o retrato atual dos SQLite; `observed_counts` descreve apenas o instante do pedido.

Promoção: `recommender-ready`, chave `ensemble`:

```json
{"schema_version":1,"event_id":"model_ready:<run_id>","type":"model.ready","run_id":"<run_id>","bundle_uri":"runs:/<run_id>/bundle","metric_name":"NDCG@10","metric_value":0.42,"trained_until_counts":{"views":100,"comments":100,"reviews":100},"created_at":"2026-09-26T12:05:00Z"}
```

O pacote só é anunciado após os três modelos e o manifesto terem sido salvos. O futuro consumidor deve deduplicar por `run_id` e acessar o mesmo armazenamento de artefatos MLflow.
