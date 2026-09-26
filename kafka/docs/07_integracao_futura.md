# 07 — Integração com treinamento

O Compose da raiz reutiliza os três tópicos e consumidores Kafka, mas publica uma amostra Yelp com IDs reais em vez dos eventos sintéticos. A variável `MATRIX_DATA_DIR` isola seus SQLite em `kafka/data/yelp`; o Compose deste diretório continua usando `kafka/data` por padrão.

O treinador Python lê as matrizes em modo de leitura, copia um retrato estável de cada banco e transforma `view_count`, `comment_text` e `stars` em três datasets RecBole. Após a carga inicial, um monitor publica pedidos em `recommender-retrain`. Quando um conjunto dos três modelos supera o campeão, o treinador anuncia `recommender-ready`. Os dois tópicos adicionais são criados pelo Compose da raiz.

O contrato e os comandos atuais estão em [`recommender_training`](../../recommender_training/README.md). O arquivo SQLite de cada tipo conserva `processed_events`, de modo que replays com `event_id` estável não duplicam os sinais.
