# 05 — Implementação e validação

O projeto Python usa `pyproject.toml`, `uv.lock` e `.python-version` com uv; não usa `requirements.txt`. O código fica em `src/data/` (amostra e retratos), `src/models/` (NeuMF e ranking), `src/messaging/` (Kafka) e `src/orchestration/` (CLI, estado e ciclo de treino). Arquivos Yelp brutos e gerados não são versionados. A imagem Docker sincroniza o ambiente a partir do lockfile.

O Compose da raiz inclui o Compose Kafka e acrescenta MLflow, preparador, replay inicial e posterior, monitor e trabalhador. Os produtores Java sintéticos usam o perfil `synthetic`, disponível com `docker compose --profile synthetic` no diretório `kafka/`. A variável `MATRIX_DATA_DIR` aponta as matrizes da raiz para `kafka/data/yelp`; o Compose Kafka isolado usa `kafka/data` por padrão.

Critérios de aceite:

1. O preparador produz exatamente 100 usuários, 300 restaurantes, 100 pares de validação e 100 de teste; nenhum desses pares entra no Kafka.
2. Um evento repetido não altera a matriz; a carga inicial completa precede o primeiro pedido de treino.
3. Os três modelos treinam com `.inter` derivados do SQLite, registram métricas com `uni10` e podem ser carregados novamente para recomendar.
4. O replay posterior provoca retreino sobre o histórico acumulado. O primeiro pacote é anunciado; candidatos empatados ou piores conservam o campeão.
5. `docker compose up --build -d` sobe o fluxo sem backend ou frontend; as CLI `status` e `recommend` permitem inspecioná-lo.
