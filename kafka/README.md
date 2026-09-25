# Infraestrutura Kafka do Taste Match

Este diretório contém um ambiente local completo com três brokers Kafka, três produtores Java e três consumidores Java. Os produtores geram interações sintéticas de visualização, comentário e avaliação. Os consumidores mantêm matrizes usuário–restaurante em bancos SQLite persistidos em `data/`.

## Início rápido

Pré-requisito: Docker com o plugin Docker Compose.

```bash
cd kafka
docker compose up --build -d
docker compose ps
docker compose logs -f view-producer view-matrix-consumer
```

Depois de alguns segundos, os arquivos `data/views.db`, `data/comments.db` e `data/reviews.db` serão criados. Para encerrar preservando os dados:

```bash
docker compose down
```

Consulte o roteiro completo em [03_execucao.md](docs/03_execucao.md).

## Componentes

| Fluxo | Tópico | Produtor | Consumidor | Matriz |
| --- | --- | --- | --- | --- |
| Visualizações | `view-restaurant` | `view-producer` | `view-matrix-consumer` | `data/views.db` |
| Comentários | `comment-restaurant` | `comment-producer` | `comment-matrix-consumer` | `data/comments.db` |
| Avaliações | `review-restaurant` | `review-producer` | `review-matrix-consumer` | `data/reviews.db` |

Cada tópico possui três partições, fator de replicação 3 e `min.insync.replicas=2`.

## Documentação

1. [Arquitetura](docs/01_arquitetura.md)
2. [Contratos de eventos](docs/02_contratos_de_eventos.md)
3. [Execução](docs/03_execucao.md)
4. [Produtores e consumidores](docs/04_produtores_e_consumidores.md)
5. [Matrizes SQLite](docs/05_matrizes_sqlite.md)
6. [Validação](docs/06_validacao.md)
7. [Integração futura](docs/07_integracao_futura.md)
