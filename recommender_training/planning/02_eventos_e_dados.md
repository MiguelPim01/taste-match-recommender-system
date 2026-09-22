# 02 — Eventos e dados

## Contrato Kafka

Usar JSON UTF-8. O tópico de entrada é `restaurant.interactions.v1`; a chave Kafka é `user_id`. Todos os eventos trazem `schema_version: 1`, `event_id` único, `type`, `user_id`, `restaurant_id` e `occurred_at` em UTC no formato ISO 8601. A aplicação produtora deve manter os mesmos IDs do catálogo usado pelo treino. Campos adicionais podem ser ignorados pelo consumidor; evento sem campo obrigatório ou com tipo/valor inválido deve ser registrado como erro, ter seu offset confirmado e não entrar nas matrizes, para não bloquear a fila.

Exemplos mínimos:

```json
{"schema_version":1,"event_id":"view:42","type":"restaurant.viewed","user_id":"u1","restaurant_id":"r1","occurred_at":"2026-09-22T12:00:00Z"}
{"schema_version":1,"event_id":"review:7:rated","type":"restaurant.rated","user_id":"u1","restaurant_id":"r1","occurred_at":"2026-09-22T12:01:00Z","stars":5}
{"schema_version":1,"event_id":"review:7:commented","type":"restaurant.commented","user_id":"u1","restaurant_id":"r1","occurred_at":"2026-09-22T12:01:00Z","text":"Excellent food and friendly staff."}
```

`stars` é inteiro de 1 a 5; `text` é uma string não vazia. A visualização não leva valor adicional: cada evento válido soma uma visualização. O `event_id` é estável numa reprodução do mesmo dado. A chave por usuário facilita preservar a ordem dos eventos daquele usuário; a escolha do último comentário/avaliação usa `occurred_at` e, em empate, `event_id`, sem depender da ordem de chegada.

O tópico de saída é `recommender.model.ready.v1`; a chave é `ensemble`. O evento significa que o pacote está completo e venceu a validação:

```json
{"schema_version":1,"event_id":"model_ready:<run_id>","type":"model.ready","run_id":"<run_id>","bundle_uri":"runs:/<run_id>/bundle","metric_name":"NDCG@10","metric_value":0.42,"trained_until_event_seq":1200,"created_at":"2026-09-22T12:05:00Z"}
```

O consumidor usa `run_id` para deduplicar e busca o pacote no MLflow. `trained_until_event_seq` é a sequência local máxima incluída no retrato de treino; não é um offset Kafka. O acesso aos artefatos requer a mesma instância de MLflow ou um armazenamento compartilhado.

## Origem e separação dos dados

`prepare-yelp` lê `yelp_academic_dataset_business.json` e `yelp_academic_dataset_review.json` linha a linha. Usa `business_id` e `categories` do primeiro arquivo para filtrar estabelecimentos cuja categoria inclui `Restaurants`; usa `review_id`, `user_id`, `business_id`, `stars`, `text` e `date` do segundo. Mantém IDs originais e limita a amostra a até 10 mil reviews por padrão, com limite configurável para caber em máquina comum. Dados brutos permanecem fora do Git.

Ordenar os reviews selecionados por data e `review_id`, separar 80% iniciais para `seed`, 10% seguintes para `live` e 10% finais para validação. Cada review de `seed` ou `live` gera um evento de avaliação e outro de comentário. Gerar de 1 a 3 visualizações sintéticas por review desses grupos: `1 + (inteiro de SHA-256(review_id) mod 3)`, com instantes anteriores ao review e IDs estáveis. Nenhum evento da validação entra no Kafka ou no treino. O resumo do preparador deve registrar tamanho da amostra, quantidade de usuários/restaurantes e cobertura da validação. Se a amostra não permitir avaliar usuários e restaurantes conhecidos no histórico inicial, a preparação deve falhar com orientação para ampliar a amostra.

## Persistência e matrizes

SQLite guarda os eventos aceitos, com `event_id` único, sequência local crescente e os dados necessários para reconstruir um retrato de treino. Gravar em transação antes do commit do offset Kafka; uma reentrega não altera contagens. O último treino bem-sucedido registra sua sequência máxima. Não é necessário um banco para cada matriz.

Ao reconstruir as matrizes esparsas por par `(user_id, restaurant_id)`:

| Sinal | Valor guardado | Consolidação de vários eventos |
| --- | --- | --- |
| Avaliação | Inteiro de 1 a 5 | Última avaliação pelo instante e ID do evento |
| Comentário | `compound` de −1 a 1, obtido com VADER | Último comentário pelo instante e ID do evento |
| Visualização | Inteiro não negativo | Contagem de eventos únicos |

Par sem interação fica ausente, não recebe zero artificial. O texto do comentário pode ser guardado apenas enquanto for necessário para calcular o sentimento; o valor `compound` e a referência ao evento bastam para o treino. O arquivo local de validação e as divisões `seed`/`live` são produzidos pelo preparador e não são redivididos a cada retreino.
