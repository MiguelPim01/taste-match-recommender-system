# 05 — Implementação e validação

## Organização futura do código

Manter um pacote Python pequeno em `recommender_training/`, com ponto de entrada `cli.py` e responsabilidades separadas:

```text
recommender_training/
├── README.md
├── planning/                # decisões e contratos desta etapa
├── requirements.txt         # versões testadas de RecBole, VADER, MLflow e Kafka
├── __init__.py              # pacote Python importável
├── cli.py                   # prepare-yelp, replay, consume e train --force
├── events.py                # validação dos dois contratos JSON e Kafka
├── storage.py               # eventos únicos, estado de treino e aviso pendente em SQLite
├── dataset.py               # amostra Yelp, divisão fixa e matrizes/arquivos .inter
├── training.py              # três execuções NeuMF e avaliação
├── ranking.py               # ensemble e fallback; compartilhável com o consumidor
├── promotion.py             # MLflow, comparação, pacote e promoção
└── data/                    # estado local não versionado
```

Classes centrais sugeridas: `EventStore` concentra transações SQLite e deduplicação; `DatasetBuilder` prepara os retratos e usa VADER; `TrainingPipeline` coordena três treinos e a validação; `EnsembleRanker` centraliza a mesma regra de pontuação usada na avaliação e no serviço; `PromotionService` registra o bundle e decide/publica a promoção. Adaptadores Kafka e CLI chamam essas classes, sem lógica de modelo dentro dos handlers. Evitar hierarquias, fábrica de modelos ou serviço web só para o treinamento.

## Ordem de implementação

1. Preparar a amostra do Yelp, o contrato JSON e a persistência idempotente; confirmar que a validação nunca vira evento de treino.
2. Gerar as três matrizes e os `.inter`; treinar os três NeuMF com configurações pequenas e salvar um bundle que seja carregável depois de reiniciar o processo.
3. Implementar o ranking combinado e NDCG@10 fixo; conferir que o mesmo bundle reproduz a mesma lista antes e depois de ser recuperado do MLflow.
4. Acrescentar o ponteiro da melhor versão, o gatilho por volume e a publicação recuperável de `model.ready`.
5. Completar o README com comandos reais, configuração de Kafka/MLflow, arquivos de dados e um roteiro curto da demonstração.

## Verificações de aceite

- Um replay determinístico publica avaliação, comentário e visualização; o consumidor grava cada `event_id` uma vez, inclusive após reinício ou reentrega.
- Uma avaliação 2, um comentário negativo e uma visualização única ficam nas matrizes, mas não são tratados como interações positivas do NeuMF. Avaliação 5, comentário positivo e duas visualizações entram nos respectivos `.inter`.
- O primeiro `train --force` registra três modelos, métricas e manifesto no mesmo run MLflow; o pacote recuperado produz ranking para um usuário conhecido.
- Após `RETRAIN_MIN_EVENTS` eventos novos, ocorre um único retreino. Um candidato melhor gera exatamente uma nova promoção lógica; empate ou piora mantém o `champion_run_id`.
- Interromper a publicação e retomá-la não perde o evento `model.ready`; receber o mesmo `run_id` duas vezes não recarrega a versão no consumidor.
- O roteiro da equipe demonstra, além deste módulo, as três situações de interesse e ações pedidas pelo Trabalho 1.

Antes de implementar, conferir versões mutuamente compatíveis de Python, PyTorch, RecBole e MLflow e fixá-las em `requirements.txt`. A máquina local identificada no planejamento usa Python 3.10.12. Não incluir o dataset completo nem bancos/artefatos gerados no Git.
