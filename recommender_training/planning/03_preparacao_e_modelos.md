# 03 — Preparação e modelos

## Sentimento e sinais positivos

Usar `vaderSentiment.SentimentIntensityAnalyzer` e sua chave `compound` para comentários em inglês. O valor fica entre −1 e 1; o limiar positivo escolhido é `compound >= 0.05`. Comentários vazios são inválidos, e comentário neutro ou negativo permanece registrado, mas não vira interação positiva no NeuMF. Essa regra é de classificação de sentimento, não uma nota de restaurante: ironia, textos longos e comentários multilíngues podem gerar resultados inadequados. [Referência do VADER](https://github.com/cjhutto/vaderSentiment).

As matrizes documentam os valores originais. Para o RecBole, gerar três arquivos de interações positivas, um para cada fonte:

| Modelo NeuMF | Par usuário–restaurante entra no treino quando |
| --- | --- |
| `ratings` | Última avaliação é 4 ou 5 |
| `comments` | Último `compound` é ≥ 0,05 |
| `views` | Contagem de visualizações é ≥ 2 |

RecBole recebe um `.inter` por modelo, com `user_id:token`, `item_id:token` e, se necessário para o corte temporal, `timestamp:float`. Não enviar a nota 1–5, o sentimento −1–1 ou a contagem como se fossem o rótulo binário do NeuMF: o modelo é treinado com interações positivas e amostras negativas geradas pelo RecBole. Avaliação baixa ou sentimento negativo ficam fora do conjunto positivo; não são convertidos em preferência positiva por engano. Manter uma configuração compartilhada e conservadora de NeuMF, amostragem negativa, épocas máximas, seed e avaliação. Não fazer busca de hiperparâmetros na primeira entrega. [NeuMF no RecBole](https://recbole.io/docs/_modules/recbole/model/general_recommender/neumf.html), [arquivos de entrada](https://recbole.io/atomic_files.html).

Treinar com os eventos até `trained_until_event_seq`. Um retrato pode ter alguns pares presentes em apenas uma ou duas fontes; cada modelo usa seus próprios IDs conhecidos. Se uma fonte não tiver pares suficientes para treinar, a execução falha de modo explícito e mantém o conjunto atual. A demonstração deve escolher uma amostra que permita os três treinos. Os limites de amostra e de épocas serão configuráveis, com valores pequenos para ambiente local.

## Combinação das recomendações

Cada NeuMF gera uma lista ordenada dos restaurantes que consegue pontuar para o usuário. Combinar as listas por soma de posições recíprocas ponderadas, evitando somar probabilidades de modelos com escalas diferentes:

`score(item) = Σ peso_fonte / (60 + posição_fonte(item))`.

Pesos iniciais: avaliações `0.50`, comentários `0.30`, visualizações `0.20`. Se um usuário não existir em um modelo, descartar esse modelo e normalizar os pesos dos restantes para somarem 1. Um restaurante que não existe no vocabulário de uma fonte não recebe parcela daquela fonte. Em caso de empate, ordenar por `restaurant_id`. Remover da resposta os restaurantes com avaliação conhecida de 1 ou 2 e os já observados no retrato de treino. Se o usuário não tiver histórico em nenhum modelo, retornar restaurantes populares por contagem de avaliações positivas do treino, com desempate por ID. Este fallback não é um quarto modelo treinado.

O pacote de artefatos precisa incluir os três checkpoints, as configurações e os mapeamentos de IDs necessários para reproduzir a pontuação, além dos pesos, catálogo, histórico de pares já observados, pares com avaliação baixa, lista de popularidade e metadados do retrato. O consumidor de recomendações usa esse mesmo algoritmo; não precisa treinar modelos.

## Validação e comparação

Congelar a validação produzida por `prepare-yelp` antes de qualquer replay. São relevantes para NDCG@10 as avaliações 4–5 de usuários e restaurantes já conhecidos no grupo `seed`; registrar quantos usuários e pares foram elegíveis. Para cada usuário elegível, ranquear os restaurantes do catálogo, desconsiderando os itens vistos no retrato de treino, e considerar relevantes os itens positivos da validação. Calcular NDCG@10 médio entre esses usuários. A mesma validação, mesmo catálogo inicial e mesma regra de elegibilidade servem para todas as execuções, permitindo comparar candidato e versão atual. Eventos posteriores podem ampliar o vocabulário para servir recomendações, mas novos IDs não entram na comparação fixa.

Registrar no MLflow NDCG@10 do ensemble, métricas dos três modelos, cobertura da validação, número de interações positivas por fonte, pesos e sequência máxima do retrato. A métrica principal de promoção é apenas NDCG@10 do ensemble. Ela mede o desempenho no subconjunto observável da amostra, não prova qualidade para usuários novos nem substitui uma avaliação posterior com dados reais de visualização.
