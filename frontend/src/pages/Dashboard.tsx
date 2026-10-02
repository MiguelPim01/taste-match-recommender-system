import { useCallback, useEffect, useRef, useState } from "react";

import { api, errorMessage, newActionKey, type Dashboard as DashboardData } from "../api";
import { Meter, MinuteColumns, ModelTrend } from "../components/charts";
import { Icon } from "../components/Icon";
import { TicketRail, type TicketData } from "../components/Tickets";
import { REQUEST_SOURCE, formatClock, formatInteger, formatMetric, formatShortClock, plural } from "../format";
import { useLiveEvent } from "../live";

type Retrain =
  | { state: "idle" }
  | { state: "sending" }
  | { state: "requested"; eventId: string }
  | { state: "training" }
  | { state: "done"; runId: string }
  | { state: "failed"; message: string };

const RETRAIN_TEXT: Partial<Record<Retrain["state"], string>> = {
  sending: "Enviando o pedido…",
  requested: "Pedido gravado no Kafka. Esperando chegar ao tópico de treino…",
  training: "O pedido está no tópico recommender-retrain e o worker está treinando.",
};

const TOTALS = [
  { key: "views", label: "Visualizações", className: "tile-views", icon: "view" },
  { key: "comments", label: "Comentários", className: "tile-comments", icon: "comment" },
  { key: "reviews", label: "Avaliações", className: "tile-reviews", icon: "rating" },
] as const;

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tickets, setTickets] = useState<TicketData[]>([]);
  const [retrain, setRetrain] = useState<Retrain>({ state: "idle" });
  const lastLoad = useRef(0);

  const load = useCallback(() => {
    lastLoad.current = Date.now();
    api.dashboard().then((value) => {
      setData(value);
      setError(null);
    }, (reason) => setError(errorMessage(reason)));
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  useLiveEvent("activity", (event) => {
    const receivedAt = new Date().toISOString();
    const arrived = [...event.recent].reverse().map((item) => ({ ...item, received_at: receivedAt }));
    setTickets((current) => [...arrived, ...current.filter((ticket) => !arrived.some((item) => item.event_id === ticket.event_id))].slice(0, 14));
    if (Date.now() - lastLoad.current > 2000) load();
  });
  useLiveEvent("retrain.requested", (event) => {
    setRetrain((step) => (step.state === "requested" && step.eventId === event.event_id ? { state: "training" } : step));
    load();
  });
  useLiveEvent("model.ready", (event) => {
    setRetrain((step) => (step.state === "requested" || step.state === "training" ? { state: "done", runId: event.run_id } : step));
    load();
  });

  async function requestRetrain() {
    setRetrain({ state: "sending" });
    try {
      const { event_id } = await api.retrain(newActionKey());
      setRetrain({ state: "requested", eventId: event_id });
    } catch (reason) {
      setRetrain({ state: "failed", message: errorMessage(reason) });
    }
  }

  if (!data) {
    return <main className="page">{error ? <p className="error" role="alert">{error}</p> : <p className="quiet">Carregando o painel…</p>}</main>;
  }

  const { next_training: next, current_model: model } = data;
  // Live tickets first, then the latest events the projection already holds, newest first.
  const known = data.recent_events.map((event) => ({ ...event, received_at: event.recorded_at }));
  const rail = [...tickets, ...known.filter((event) => !tickets.some((ticket) => ticket.event_id === event.event_id))]
    .sort((a, b) => b.received_at.localeCompare(a.received_at))
    .slice(0, 14);
  return (
    <main className="page dashboard">
      <header className="page-head">
        <h1>Painel</h1>
        <p className="lede">
          Cada visualização, comentário e avaliação vira um evento no Kafka. A cada {formatInteger(next.threshold)} eventos
          novos, o monitor publica um pedido de treino; o modelo novo entra em uso e recalcula as listas de todos os perfis.
        </p>
      </header>
      {error && <p className="error" role="alert">{error}</p>}

      <section className="cycle" aria-label="Ciclo de treino">
        <div className="cycle-next">
          <p className="hero-figure">{formatInteger(next.remaining)}</p>
          <p className="hero-caption">
            {next.remaining === 0
              ? "eventos faltando. O monitor pede o próximo treino na verificação seguinte, a cada 10 segundos."
              : `${next.remaining === 1 ? "evento novo falta" : "eventos novos faltam"} para o próximo treino`}
          </p>
          <Meter value={next.new_events} max={next.threshold} label="Eventos novos desde o modelo em uso" />
          <p className="quiet">
            {formatInteger(next.new_events)} de {formatInteger(next.threshold)} desde o modelo em uso.
            {data.request_after_last_model && " Há um pedido de treino na fila."}
          </p>
        </div>
        <div className="cycle-model">
          <h2>Modelo em uso</h2>
          {model ? (
            <dl className="model-facts">
              <div><dt>Execução no MLflow</dt><dd className="mono">{model.run_id.slice(0, 8)}</dd></div>
              <div><dt>{model.metric_name} na validação</dt><dd>{formatMetric(model.metric_value)}</dd></div>
              <div><dt>Treinado com</dt><dd>{plural(model.trained_until_total, "evento", "eventos")}</dd></div>
              <div><dt>Entrou em uso</dt><dd>{formatShortClock(model.created_at)}</dd></div>
            </dl>
          ) : <p className="quiet">Nenhum modelo treinado ainda.</p>}
          <button className="button" onClick={requestRetrain}
            disabled={retrain.state === "sending" || retrain.state === "requested" || retrain.state === "training"}>
            Pedir retreino agora
          </button>
          <p className="step" role="status">
            {retrain.state === "done" && `Modelo novo em uso: ${retrain.runId.slice(0, 8)}.`}
            {retrain.state === "failed" && retrain.message}
            {RETRAIN_TEXT[retrain.state]}
            {retrain.state === "idle" && `Pede um treino sem esperar os ${formatInteger(next.threshold)} eventos novos.`}
          </p>
        </div>
      </section>

      <section className="rail-section" aria-labelledby="rail-heading">
        <div className="section-head">
          <h2 id="rail-heading">Comandas chegando</h2>
          <p className="quiet">Os últimos eventos que o backend leu dos tópicos; os novos entram pela esquerda.</p>
        </div>
        <TicketRail tickets={rail} />
      </section>

      <section className="tiles" aria-label="Totais projetados">
        {TOTALS.map((total) => (
          <div key={total.key} className={`tile ${total.className}`}>
            <p className="tile-label"><Icon name={total.icon} size={18} /> {total.label}</p>
            <p className="tile-value">{formatInteger(data.totals[total.key])}</p>
          </div>
        ))}
      </section>

      <div className="charts-grid">
        <section aria-labelledby="per-minute">
          <h2 id="per-minute">Eventos por minuto</h2>
          <p className="quiet chart-note">Últimos 15 minutos, pelo horário de publicação no Kafka.</p>
          <MinuteColumns data={data.events_per_minute} />
        </section>
        <section aria-labelledby="ndcg">
          <h2 id="ndcg">NDCG@10 de cada modelo</h2>
          <p className="quiet chart-note">Do mais antigo ao atual. Só acompanha a evolução: todo treino concluído entra em uso.</p>
          <ModelTrend models={data.models} />
        </section>
      </div>

      <section aria-labelledby="requests-heading">
        <h2 id="requests-heading">Pedidos de treino</h2>
        {data.retrain_requests.length === 0 ? <p className="quiet">Nenhum pedido ainda.</p> : (
          <div className="table-scroll">
            <table className="requests">
              <thead><tr><th>Quando</th><th>Origem</th><th>Eventos observados</th><th>Forçado</th></tr></thead>
              <tbody>
                {data.retrain_requests.map((item) => (
                  <tr key={item.event_id}>
                    <td>{formatClock(item.requested_at)}</td>
                    <td>{REQUEST_SOURCE[item.source ?? ""] ?? item.source ?? "Sem origem"}</td>
                    <td className="number">{item.observed_total === null ? "—" : formatInteger(item.observed_total)}</td>
                    <td>{item.force ? "Sim" : "Não"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
