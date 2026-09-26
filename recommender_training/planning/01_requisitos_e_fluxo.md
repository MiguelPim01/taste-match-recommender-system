# 01 — Requisitos e fluxo

O Compose da raiz une Kafka, três consumidores de matrizes SQLite, carga Yelp, monitor de retreino, treinador e MLflow. Backend e frontend ainda não existem; a CLI `recommend` consulta o pacote promovido.

```text
Yelp → amostra fixa → seed → 3 tópicos Kafka → 3 SQLite
                       live ────────────────────────┘
                                                    ↓
                                  monitor → pedido Kafka → treinador
                                                    ↓
                                  3 NeuMF → ensemble → MLflow
                                                    ↓
                                  promoção → model.ready Kafka
```

O Kafka mantém três tópicos (`view-restaurant`, `comment-restaurant`, `review-restaurant`) e três bancos. O treinamento lê esses bancos; não consome novamente os tópicos de interação nem cria o tópico agregado `restaurant.interactions.v1` do planejamento anterior. O gatilho é um evento em `recommender-retrain`. O aviso de promoção usa `recommender-ready`.

Os produtores sintéticos Java continuam no perfil `synthetic` do Compose em `kafka/`. No Compose da raiz, a carga Yelp usa IDs originais. Os bancos Yelp ficam em `kafka/data/yelp`, separados dos bancos sintéticos anteriores.

O enunciado do Trabalho 1 também pede três situações de interesse com ações; essa parte permanece responsabilidade dos outros módulos da equipe. O evento de modelo pronto é o evento derivado deste componente.
