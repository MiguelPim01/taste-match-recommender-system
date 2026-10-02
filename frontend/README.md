# Frontend do TasteMatch

App em React + Vite para usar e demonstrar o sistema: escolher um perfil, explorar os 300 restaurantes, ver, comentar e avaliar, receber recomendações e acompanhar o ciclo de treino no painel. Tudo que o app mostra vem do [backend](../backend/README.md); tudo que ele faz vira um evento no Kafka.

## Como rodar

Junto com o resto do sistema, na raiz do repositório:

```bash
docker compose up --build -d
```

O app fica em [http://localhost:3000](http://localhost:3000) (`FRONTEND_PORT` muda a porta). O container é um nginx que serve o build e repassa `/api` para o backend, então app e API ficam na mesma origem: o cookie de sessão e o stream SSE funcionam sem CORS.

Para desenvolver com recarga automática, com o backend do Compose no ar:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, com /api repassado para localhost:8000
npm run build      # checa os tipos e gera dist/
```

## Telas

| Rota | O que faz | Eventos |
| --- | --- | --- |
| `/entrar` | Escolhe um dos 100 perfis do Yelp ou cria um perfil novo | — |
| `/` | “Para você”: a lista do modelo em ordem, com a origem de cada item. O painel “Testar com interações simuladas” publica visualizações, notas boas e comentários positivos numa categoria e pode pedir um treino no final | atualiza com `recommendations.updated` e `interaction.recorded`; o painel conta as confirmações |
| `/explorar` | Catálogo com busca, categoria e ordenação | — |
| `/restaurantes/:id` | Detalhe, sua nota e comentários; abrir a página registra a visualização | cada ação passa por *enviando*, *gravado no Kafka* e *confirmado* |
| `/atividade` | Interações por categoria (barras empilhadas por tipo, com dica e tabela) e o histórico do perfil, do mais recente ao mais antigo | atualiza com `interaction.recorded` |
| `/painel` | Ciclo de treino: quanto falta para o próximo treino, modelo em uso, comandas chegando, eventos por minuto, NDCG@10 e pedidos de treino; atalho para pedir retreino | `activity`, `retrain.requested`, `model.ready` |

Uma conexão `EventSource` por perfil fica aberta em `/api/stream` (`src/live.tsx`). Quando o backend lê de volta do Kafka uma ação sua, a confirmação aparece no canto da tela como uma comanda impressa.

## Estrutura

```text
src/
├── main.tsx              fontes, rotas e provedores
├── App.tsx               barra superior e rotas; as telas do app pedem um perfil, o painel não
├── api.ts                tipos das respostas e chamadas à API (com Idempotency-Key nas ações)
├── session.tsx           perfil da sessão (cookie tm_user, definido pelo backend)
├── live.tsx              eventos SSE e o hook useLiveEvent
├── format.ts             números, datas e rótulos em pt-BR
├── styles.css            tokens de cor e tipografia e todos os estilos
├── components/           letreiros de restaurante, estrelas, comandas, gráficos e o simulador de teste
└── pages/                uma tela por rota
```

## Escolhas visuais

- **Comandas de cozinha.** Cada evento é impresso como uma comanda de papel térmico: na confirmação das suas ações e no trilho do painel, onde os eventos chegam ao vivo. É o único elemento chamativo; o resto fica sóbrio.
- **Cores.** Branco, aço e grafite, com mostarda de pretzel da Filadélfia como cor da marca. As cores dos tipos de evento (azul para visualizações, laranja para avaliações, água-marinha para comentários) passaram no validador de daltonismo do guia de gráficos, nessa ordem de empilhamento; a água-marinha tem pouco contraste com o branco, por isso todo gráfico tem legenda, dica e tabela.
- **Tipografia.** Big Shoulders Display, de letreiro, nos nomes de restaurantes e títulos; Public Sans no texto e nos números; IBM Plex Mono só nas comandas. As fontes vêm empacotadas pelo Fontsource, sem depender de internet.
- **Ícones.** Desenhados para o app (`src/icons.ts`): 22 de culinária e 3 de tipo de evento, em grade de 24px, traço de 1,75px e `currentColor`. `src/categories.ts` agrupa as 172 categorias do Yelp sob esses ícones e escolhe o emblema de cada restaurante: primeiro uma categoria que define o lugar (Cheesesteaks vence tudo, depois Public Markets, Ramen, Sushi Bars, Dim Sum, Pizza…), depois a ordem do Yelp, com rótulos amplos como Nightlife e American por último.
- **Categorias.** O emblema em mostarda fica ao lado do nome; as categorias viram etiquetas com ícone que abrem o catálogo filtrado (`/explorar?categoria=…`), com a do emblema realçada. No Explorar, uma faixa mostra a categoria mais comum de cada tipo de culinária.
