# 04 — Retreino e publicação

O replay inicial aguarda os consumidores processarem os eventos da amostra antes de marcar `seed.complete`. O monitor então publica um pedido Kafka para o primeiro treino. Após isso, conta os eventos únicos aceitos nos três `processed_events` desde o último treino completo e pede outro ao chegar a `RETRAIN_MIN_EVENTS` (padrão 300). Reentregas e eventos rejeitados não incrementam a contagem. Pedidos manuais usam `taste-match-training request-train`.

O trabalhador consome os pedidos em sequência com commit manual. Cada execução copia um retrato de cada banco e treina desde o início sobre todo o histórico acumulado, exceto validação e teste fixos. O estado SQLite local guarda contagens da última execução completa, pedido pendente, modelo em uso e avisos ainda não enviados. Falha no treino conserva o estado anterior e deixa o pedido para repetição. Antes de treinar, o trabalhador confere de novo se há ao menos `RETRAIN_MIN_EVENTS` eventos novos: pedidos repetidos que sobraram na fila são descartados, e `force: true` ignora a conferência.

O MLflow registra parâmetros, métricas e pacote `bundle/` por execução. Cada treino concluído passa a ser o modelo em uso e gera `model.ready`; o NDCG@10 de validação segue no MLflow e no aviso para acompanhar a evolução, sem decidir a troca. A troca e o aviso pendente são persistidos juntos; uma repetição da publicação Kafka não perde o aviso.

A regra anterior só trocava o modelo com melhora estrita de NDCG@10 sobre o campeão. Ela foi retirada porque a métrica oscila com a amostra de negativos (o mesmo modelo mediu 0,4877 e 0,5262 em amostras diferentes) e porque impedia perfis criados no app de ganhar recomendações: a prova só mede os 100 perfis do manifesto.

O replay posterior só começa quando existe um modelo em uso. Ele publica eventos em intervalos configuráveis para gerar novos pedidos durante a demonstração.
