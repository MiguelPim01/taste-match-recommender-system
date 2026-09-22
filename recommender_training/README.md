# Treinamento do recomendador

Este diretório contém o planejamento do componente que recebe interações de usuários via Kafka, treina três recomendadores NeuMF com RecBole, acompanha experimentos no MLflow e anuncia quando um ensemble melhor está pronto. O projeto usa avaliações e comentários em inglês do Yelp Open Dataset; por isso, a análise de sentimento prevista é feita com VADER.

**Estado atual:** esta etapa entrega apenas a documentação em [`planning/`](planning/01_requisitos_e_fluxo.md). Ainda não existem código, dependências ou comandos executáveis de treinamento neste diretório. Os comandos abaixo são a interface **prevista para a implementação**, não instruções que já funcionam no repositório.

## Fluxo e organização

1. O preparador lê `business.json` e `review.json` do Yelp, seleciona restaurantes e separa registros em dados iniciais, eventos a reproduzir e validação fixa.
2. Avaliações, comentários e visualizações simuladas são publicados em `restaurant.interactions.v1`. Um consumidor grava eventos únicos em SQLite e mantém os dados necessários às três matrizes usuário × restaurante.
3. Um comando faz o primeiro treino. Depois, o consumidor dispara novo treino a cada 100 eventos únicos desde o último treino bem-sucedido; esse número é configurável.
4. O treinamento cria três modelos NeuMF, avalia a combinação em uma validação fixa e registra métricas e artefatos no MLflow. Se o resultado melhorar o atual, atualiza o ponteiro local e publica `recommender.model.ready.v1`.

| Documento | Conteúdo |
| --- | --- |
| [`01_requisitos_e_fluxo.md`](planning/01_requisitos_e_fluxo.md) | Requisitos do trabalho, fronteiras e sequência de eventos |
| [`02_eventos_e_dados.md`](planning/02_eventos_e_dados.md) | Contratos Kafka, Yelp, simulação, persistência e matrizes |
| [`03_preparacao_e_modelos.md`](planning/03_preparacao_e_modelos.md) | VADER, RecBole, ensemble, avaliação e casos sem histórico |
| [`04_retreino_e_publicacao.md`](planning/04_retreino_e_publicacao.md) | Gatilho, MLflow, promoção e evento de modelo pronto |
| [`05_implementacao_e_validacao.md`](planning/05_implementacao_e_validacao.md) | Organização futura do código e critérios de aceite |

## Como executar após a implementação

Pré-requisitos previstos: Python 3.10, um broker Kafka em `localhost:9092`, os arquivos `yelp_academic_dataset_business.json` e `yelp_academic_dataset_review.json` obtidos no [Yelp Open Dataset](https://www.yelp.com/dataset), e espaço local para SQLite e artefatos. Os arquivos brutos não serão versionados. O MLflow deve ser acessível ao consumidor e ao processo de treino; a configuração padrão planejada é local, em `http://127.0.0.1:5000`.

Os seguintes comandos definem a interface que será implementada. Os nomes e argumentos estão especificados aqui para orientar o código, mas **ainda falharão** enquanto ele não existir:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r recommender_training/requirements.txt

mlflow server --backend-store-uri sqlite:///recommender_training/data/mlflow.db --default-artifact-root ./recommender_training/data/mlartifacts --host 127.0.0.1 --port 5000
```

Em outro terminal, com o broker e o MLflow ativos:

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
python3 -m recommender_training.cli prepare-yelp --business-json /caminho/yelp_academic_dataset_business.json --review-json /caminho/yelp_academic_dataset_review.json
python3 -m recommender_training.cli consume
```

Em um terceiro terminal, usando o mesmo ambiente:

```bash
python3 -m recommender_training.cli replay --split seed
python3 -m recommender_training.cli train --force
python3 -m recommender_training.cli replay --split live
```

`prepare-yelp` criará a validação separada e os eventos de demonstração; `replay --split seed` alimentará o histórico inicial; `train --force` fará a primeira publicação; `replay --split live` demonstrará o retreino automático. O valor `RETRAIN_MIN_EVENTS=100` poderá ser reduzido para a apresentação. A confirmação do resultado será um novo run no MLflow e uma mensagem em `recommender.model.ready.v1` **somente se** o candidato superar a versão em uso.

Os outros módulos do trabalho deverão consumir os eventos primitivos para detectar três situações de interesse. Eles também poderão consumir `recommender.model.ready.v1` para carregar o ensemble promovido; a interface está em [`02_eventos_e_dados.md`](planning/02_eventos_e_dados.md).
