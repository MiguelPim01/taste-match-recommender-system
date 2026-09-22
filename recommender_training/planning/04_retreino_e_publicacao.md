# 04 — Retreino e publicação

## Gatilho simples por volume

Depois do primeiro treino manual bem-sucedido, o consumidor conta eventos **novos e válidos** gravados em SQLite após `last_successful_train_seq`. Ao chegar a `RETRAIN_MIN_EVENTS` (padrão `100`), inicia um treino; para apresentação, pode-se configurar um valor menor. Reentregas Kafka e eventos inválidos não incrementam a contagem. Não abrir dois treinos ao mesmo tempo. O comando `train --force` permite criar o primeiro modelo e repetir um treino manualmente.

Cada execução toma a maior sequência local disponível ao começar e usa apenas eventos até essa sequência. Eventos recebidos durante o treino ficam para o próximo ciclo. Depois de um treino concluído e registrado no MLflow, atualizar `last_successful_train_seq` mesmo se o candidato não for promovido; assim, uma versão pior não provoca treinamento contínuo sobre o mesmo lote. Se qualquer etapa do treino falhar, manter o ponteiro e a sequência do último treino bem-sucedido e tentar novamente no próximo ciclo, sem perder os eventos.

## Experimentos e escolha da melhor versão

Usar um experimento MLflow, por exemplo `restaurant-ensemble`, e um run para cada treino completo dos três NeuMF. Registrar parâmetros de dados e modelos, contagens, NDCG@10, cobertura e um diretório `bundle/` com checkpoints, mapeamentos, configuração e manifesto. O manifesto identifica as três fontes, pesos, retrato e versão do formato do pacote. O URI `runs:/<run_id>/bundle` permite ao consumidor recuperar os artefatos. Um pequeno banco SQLite local mantém `champion_run_id`, `champion_ndcg` e a sequência do último treino. O MLflow é o histórico de experimentos; não é necessário usar Model Registry nesta entrega. [Artefatos por run no MLflow](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.artifacts.html).

O primeiro treino completo e avaliável vira a versão em uso. Nos seguintes, promover somente se `NDCG@10` for estritamente maior que o valor atual; empate conserva o atual. Um candidato pode ficar registrado no MLflow sem gerar `model.ready`. Antes da promoção, verificar que o pacote pode ser carregado e produzir uma lista para um usuário conhecido da validação.

## Publicação recuperável

Após a promoção, atualizar o ponteiro e inserir em SQLite uma mensagem pendente para `recommender.model.ready.v1` na mesma transação. O consumidor Kafka do módulo tenta publicar essas mensagens na inicialização e após cada treino; remove a pendência apenas quando o broker confirma. Assim, falha temporária na publicação não perde o aviso. Uma repetição do aviso é permitida e identificada por `event_id = model_ready:<run_id>`; o consumidor de recomendações deve ignorar um `run_id` que já carregou. O contrato completo está em `02_eventos_e_dados.md`.

O treinamento não publica um novo evento quando não há melhoria, quando uma das três fontes falha, quando a validação não tem exemplos elegíveis ou quando o pacote não pode ser carregado. Esses casos devem aparecer no log local e no status do run para facilitar a demonstração e o diagnóstico.
