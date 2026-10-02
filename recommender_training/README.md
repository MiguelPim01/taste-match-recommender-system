# Treinamento do recomendador

Este componente lê os três bancos SQLite dos consumidores Kafka, treina três NeuMF com RecBole e combina os rankings. O Yelp fornece a carga inicial; eventos posteriores provocam retreino. O MLflow guarda métricas e pacotes de modelos.

## Início rápido

Na raiz do repositório, com Docker Compose v2.20 ou superior:

```bash
docker compose up --build -d
docker compose logs -f yelp-sample yelp-seed-replay recommender-worker
docker compose exec recommender-worker taste-match-training status
```

A primeira execução lê `data/yelp/yelp_academic_dataset_business.json` e `data/yelp/yelp_academic_dataset_review.json` em streaming; os arquivos não entram na imagem. O preparador escolhe 300 restaurantes abertos de Filadélfia e sorteia 100 usuários com semente 42 entre os que têm ao menos 10 restaurantes distintos e 5 reviews positivos. Uma avaliação positiva por usuário fica para validação e outra para teste. O restante é dividido em carga inicial e reprodução posterior.

Depois de os consumidores persistirem a carga inicial, o monitor publica `recommender-retrain`. O treinador lê um retrato dos três bancos, treina os NeuMF e registra métricas com 10 negativos uniformes por positivo (`config/recbole.yaml`). Cada treino concluído passa a ser o modelo em uso e publica `recommender-ready`; o NDCG@10 fica registrado para acompanhar a evolução, sem decidir a troca. O replay posterior começa após o primeiro modelo e alimenta novos treinos a cada 300 eventos únicos aceitos (`RETRAIN_MIN_EVENTS`), limite que o monitor e o worker conferem.

O retrato inclui os 100 usuários do manifesto e os perfis criados no app que têm interações positivas; cada fonte conhece só os perfis com positivos nela, e o ensemble ignora as fontes que não conhecem o usuário. A cada `recommender-ready`, o `recommendation-publisher` carrega o pacote do modelo novo, ranqueia todos os perfis que ele conhece e publica uma lista de 50 restaurantes por perfil em `user-recommendations` (`RECOMMENDATION_LIMIT`), tópico compactado com chave `user_id` que o backend consome.

O MLflow fica em [http://localhost:5000](http://localhost:5000). Para consultar o modelo:

```bash
docker compose exec recommender-worker taste-match-training sample-user
docker compose exec recommender-worker taste-match-training recommend --user-id ID_DO_USUARIO --limit 10
docker compose exec recommender-worker taste-match-training request-train
```

O primeiro comando imprime um ID real da amostra; use-o no segundo. `request-train --force` executa mesmo sem dados novos. `docker compose down` preserva os volumes de modelos e Kafka. O Compose da raiz guarda matrizes Yelp em `kafka/data/yelp`, separadas das matrizes sintéticas em `kafka/data`.

## Desenvolvimento com uv

O projeto usa `pyproject.toml`, `uv.lock` e `.python-version`; não há `requirements.txt`. Com uv instalado no host:

```bash
cd recommender_training
uv sync --locked
uv run taste-match-training prepare-yelp
uv run taste-match-training --help
```

O código está em `src/data/`, `src/models/`, `src/messaging/` e `src/orchestration/`. Dados Yelp brutos, ambiente virtual e estado gerado ficam fora do Git. Os comandos `status` e `recommend` do Compose devem ser executados dentro do container, que tem acesso ao volume compartilhado do MLflow. Para publicar eventos pela CLI no host, configure `KAFKA_BOOTSTRAP_SERVERS=localhost:29192,localhost:39192,localhost:49192`.

## Documentação

- [Fluxo e requisitos](planning/01_requisitos_e_fluxo.md)
- [Eventos e dados](planning/02_eventos_e_dados.md)
- [Preparação e modelos](planning/03_preparacao_e_modelos.md)
- [Retreino e publicação](planning/04_retreino_e_publicacao.md)
- [Implementação e validação](planning/05_implementacao_e_validacao.md)
