# 02 — Contratos de eventos

Todos os eventos são JSON UTF-8, usam `schema_version: 1` e são publicados com `user_id` como chave Kafka. Datas usam UTC no formato ISO 8601. Campos desconhecidos são ignorados para permitir evolução compatível.

## Visualização

Tópico `view-restaurant`, tipo `restaurant.viewed`:

```json
{
  "schema_version": 1,
  "event_id": "view-0d705f27-37a3-4a6d-a876-f8a915291901",
  "type": "restaurant.viewed",
  "user_id": "user-1",
  "restaurant_id": "restaurant-3",
  "occurred_at": "2026-09-25T12:00:00Z"
}
```

Cada `event_id` válido e ainda não processado soma uma visualização ao par usuário–restaurante.

## Comentário

Tópico `comment-restaurant`, tipo `restaurant.commented`. `text` deve ser uma string não vazia:

```json
{
  "schema_version": 1,
  "event_id": "comment-2be9e175-0706-476b-a61f-9c1ec0965e35",
  "type": "restaurant.commented",
  "user_id": "user-1",
  "restaurant_id": "restaurant-3",
  "occurred_at": "2026-09-25T12:01:00Z",
  "text": "Excellent food and friendly staff."
}
```

## Avaliação

Tópico `review-restaurant`, tipo `restaurant.rated`. `stars` deve ser inteiro entre 1 e 5:

```json
{
  "schema_version": 1,
  "event_id": "review-a6a0364e-594b-4501-8a48-a11ee0f1ed01",
  "type": "restaurant.rated",
  "user_id": "user-1",
  "restaurant_id": "restaurant-3",
  "occurred_at": "2026-09-25T12:02:00Z",
  "stars": 5
}
```

## Rejeição

São rejeitados JSON malformado, campo obrigatório ausente, versão ou tipo incorreto, nota fora do intervalo e chave Kafka diferente de `user_id`. A rejeição é registrada em `rejected_events` e o offset é confirmado. Assim uma mensagem defeituosa não bloqueia a partição.
