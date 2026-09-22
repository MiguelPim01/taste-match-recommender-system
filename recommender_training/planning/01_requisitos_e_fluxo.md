# 01 — Requisitos e fluxo

## Objetivo da primeira entrega

O [enunciado do Trabalho 1](../../docs/trabalho_1/enunciado.pdf) pede um sistema orientado a eventos com Kafka: eventos primitivos devem ser consumidos continuamente, no mínimo três situações de interesse devem produzir ações, e ao menos um consumidor deve inferir e publicar um evento derivado. Fontes reais são preferidas; quando não houver dados para uma atividade, a simulação em tempo real é permitida.

Este componente cuida exclusivamente do aprendizado a partir das interações e do anúncio de uma versão melhor do recomendador. A detecção e as ações para as três situações de interesse ficam com os outros módulos da equipe; **três tipos de evento não equivalem, por si, a três situações detectadas**. A equipe precisa definir e demonstrar essas situações separadamente. O treinamento publica `recommender.model.ready.v1`, um evento derivado das interações; o módulo que serve recomendações deverá reagir a ele carregando os artefatos da versão promovida.

## Fluxo previsto

```text
Yelp (avaliações + comentários) ─┐
                                 ├─> Kafka: restaurant.interactions.v1
Visualizações simuladas ─────────┘                  │
                                                    ▼
                                   consumidor de treinamento → SQLite
                                                    │
                                  treino inicial ou gatilho por volume
                                                    │
                                                    ▼
                                  3 × NeuMF → ensemble → validação fixa
                                                    │
                                   MLflow + ponteiro local se melhorar
                                                    │
                                                    ▼
                                    Kafka: recommender.model.ready.v1
                                                    │
                                                    ▼
                                       consumidor de recomendações
```

O consumidor grava um evento antes de confirmar seu deslocamento no Kafka. IDs de evento tornam a gravação idempotente quando há reentrega. Treinos são sequenciais: o consumidor continua podendo acumular eventos enquanto um treino usa um retrato consistente do banco. A publicação do modelo pronto só ocorre depois de os três artefatos estarem disponíveis.

## Fronteiras e decisões

- Yelp fornece `business_id`, avaliações e textos de reviews; o projeto os associa ao `restaurant_id` e `user_id` usados nos eventos. Visualizações são sintéticas, pois não há histórico de abertura de páginas nessa fonte.
- VADER substitui LeIA para os comentários em inglês. O resultado `compound` continua na faixa de −1 a 1.
- O ensemble é a unidade promovida: não se publica apenas um dos três modelos isolados. MLflow registra a experiência; SQLite guarda qual `run_id` está em uso.
- A implantação é local e educacional: um broker, um consumidor de treinamento, um banco SQLite e um servidor MLflow. Sem serviços de orquestração ou busca de hiperparâmetros nesta entrega.
- A integração com backend precisa de IDs iguais aos usados no treino, acesso aos artefatos do MLflow e reação idempotente ao evento de modelo pronto. Usuários e restaurantes novos terão o tratamento descrito em `03_preparacao_e_modelos.md`.

## Condição de demonstração do Trabalho 1

Mostrar a produção e o consumo dos três tipos de interação, o gatilho de retreino, a publicação do evento derivado e a reação do consumidor desse evento. A equipe deve mostrar separadamente as três situações de interesse e respectivas ações exigidas pelo enunciado; elas não estão implementadas neste componente.
