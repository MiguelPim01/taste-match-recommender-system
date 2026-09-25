# 05 — Matrizes SQLite

Os bancos são criados automaticamente em `kafka/data`:

| Banco | Tabela da matriz | Valor por `(user_id, restaurant_id)` |
| --- | --- | --- |
| `views.db` | `view_matrix` | `view_count` |
| `comments.db` | `comment_matrix` | `comment_text` mais recente |
| `reviews.db` | `review_matrix` | `stars` mais recente |

Cada banco também contém `processed_events`, o histórico deduplicado aceito, e `rejected_events`, que guarda payload e motivo de mensagens inválidas. O modo WAL é ativado para que futuras leituras do treinamento não bloqueiem a escrita do consumidor.

Com o cliente `sqlite3` instalado no host:

```bash
sqlite3 -header -column data/views.db \
  'SELECT user_id, restaurant_id, view_count FROM view_matrix ORDER BY user_id, restaurant_id;'

sqlite3 -header -column data/comments.db \
  'SELECT user_id, restaurant_id, comment_text FROM comment_matrix ORDER BY user_id, restaurant_id;'

sqlite3 -header -column data/reviews.db \
  'SELECT user_id, restaurant_id, stars FROM review_matrix ORDER BY user_id, restaurant_id;'
```

Para conferir processamento e rejeições:

```bash
sqlite3 data/views.db 'SELECT COUNT(*) AS processed FROM processed_events;'
sqlite3 data/reviews.db 'SELECT topic, partition_id, record_offset, reason FROM rejected_events;'
```

Não edite os bancos enquanto os consumidores estiverem ativos. Um processo futuro de treinamento deve abrir uma conexão separada e obter um retrato consistente por transação de leitura.
