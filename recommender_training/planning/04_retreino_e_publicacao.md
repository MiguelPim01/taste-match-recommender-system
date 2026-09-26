# 04 — Retreino e publicação

O replay inicial aguarda os consumidores processarem os eventos da amostra antes de marcar `seed.complete`. O monitor então publica um pedido Kafka para o primeiro treino. Após isso, conta os eventos únicos aceitos nos três `processed_events` desde o último treino completo e pede outro ao chegar a `RETRAIN_MIN_EVENTS` (padrão 300). Reentregas e eventos rejeitados não incrementam a contagem. Pedidos manuais usam `taste-match-training request-train`.

O trabalhador consome os pedidos em sequência com commit manual. Cada execução copia um retrato de cada banco e treina desde o início sobre todo o histórico acumulado, exceto validação e teste fixos. O estado SQLite local guarda contagens da última execução completa, pedido pendente, campeão e avisos de promoção ainda não enviados. Falha no treino conserva o estado anterior e deixa o pedido para repetição. Candidatos válidos que não melhoram ainda atualizam as contagens, evitando retreinar indefinidamente o mesmo lote.

O MLflow registra parâmetros, métricas e pacote `bundle/` por execução. O primeiro pacote válido é promovido. Depois, o campeão é reavaliado sobre os mesmos candidatos amostrados do novo modelo; apenas melhoria estrita em NDCG@10 promove. Promoção e aviso pendente são persistidos juntos; uma repetição da publicação Kafka não perde o aviso. Empates e pioras não geram `model.ready`.

O replay posterior só começa quando existe um campeão. Ele publica eventos em intervalos configuráveis para gerar novos pedidos durante a demonstração.
