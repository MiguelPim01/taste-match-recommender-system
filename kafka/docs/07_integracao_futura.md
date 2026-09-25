# 07 — Integração futura

## Entrada dos modelos

Os bancos SQLite separam os três sinais da arquitetura:

- Modelo A lê `view_matrix.view_count`.
- Modelo B lê `comment_matrix.comment_text` e calcula sentimento na preparação do treinamento.
- Modelo C lê `review_matrix.stars`.

O treinamento deverá abrir os três bancos em modo de leitura, capturar um retrato consistente e manter os mesmos `user_id` e `restaurant_id`. Comentários continuam em inglês porque os dados reais planejados vêm do Yelp; a análise VADER prevista em `recommender_training` permanece adequada.

## Diferença para o planejamento anterior

O planejamento em `recommender_training` menciona o tópico agregado `restaurant.interactions.v1`. A implementação Kafka atual adotou os três tópicos definidos pelo diagrama. Quando o treinamento for implementado, ele deverá escolher uma destas integrações:

1. Ler diretamente os três bancos desta etapa, opção mais simples para treinamento em lote.
2. Consumir os três tópicos com um único processo e reconstruir seu armazenamento próprio, opção adequada para retreinamento contínuo.

Não é necessário criar o tópico agregado. Os campos comuns e as regras de identificação já são compatíveis com o contrato planejado; muda apenas a separação física por tipo de interação.

## Saída futura

Depois do treinamento dos três modelos, o ensemble será promovido e publicará `recommender.model.ready.v1`, conforme a documentação em `recommender_training`. Esse tópico e seu consumidor não fazem parte do Compose atual.
