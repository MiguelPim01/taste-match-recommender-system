import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, errorMessage, newActionKey, type Category, type Simulation } from "../api";
import { formatInteger, plural } from "../format";
import { useLiveEvent } from "../live";

type Training = "off" | "requested" | "failed" | "done";

type Run =
  | { state: "idle" }
  | { state: "sending" }
  | { state: "sent"; result: Simulation; confirmed: number; training: Training }
  | { state: "failed"; message: string };

const SIZES = [3, 6, 10];

/** Test tool for "Para você": real events for one category, published through the API and Kafka like the app's own. */
export function SimulationPanel() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState("");
  const [size, setSize] = useState(6);
  const [retrain, setRetrain] = useState(true);
  const [run, setRun] = useState<Run>({ state: "idle" });
  // Confirmations can arrive before the request returns, so every recorded event is remembered.
  const recorded = useRef(new Set<string>());

  useEffect(() => {
    api.categories().then((list) => {
      const usable = list.filter((item) => item.count >= 3).sort((a, b) => a.name.localeCompare(b.name));
      setCategories(usable);
      setCategory((current) => current || (usable.find((item) => item.name === "Pizza") ?? usable[0])?.name || "");
    }, (reason) => setRun({ state: "failed", message: errorMessage(reason) }));
  }, []);

  const confirmedOf = (result: Simulation) => result.event_ids.filter((id) => recorded.current.has(id)).length;

  useLiveEvent("interaction.recorded", (event) => {
    recorded.current.add(event.event_id);
    setRun((current) => (current.state === "sent" ? { ...current, confirmed: confirmedOf(current.result) } : current));
  });
  useLiveEvent("recommendations.updated", () => {
    setRun((current) => (current.state === "sent" && current.training === "requested" ? { ...current, training: "done" } : current));
  });

  async function simulate(event: FormEvent) {
    event.preventDefault();
    setRun({ state: "sending" });
    let result: Simulation;
    try {
      result = await api.simulate(category, size);
    } catch (reason) {
      setRun({ state: "failed", message: errorMessage(reason) });
      return;
    }
    let training: Training = "off";
    if (retrain) {
      training = await api.retrain(newActionKey()).then(() => "requested" as const, () => "failed" as const);
    }
    setRun({ state: "sent", result, confirmed: confirmedOf(result), training });
  }

  return (
    <details className="simulation">
      <summary className="button button-quiet">Testar com interações simuladas</summary>
      <div className="simulation-body">
        <p>
          Para cada restaurante, publica uma visualização, uma nota 4 ou 5 e um comentário positivo, em inglês porque o
          treino só lê sentimento em inglês. Os eventos passam pela API e pelo Kafka como as suas ações. Restaurantes que
          você ainda não abriu vêm primeiro; o resto da categoria fica para o modelo recomendar.
        </p>
        <form className="simulation-form" onSubmit={simulate}>
          <label>
            Categoria
            <select value={category} onChange={(change) => setCategory(change.target.value)}>
              {categories.map((item) => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}
            </select>
          </label>
          <label>
            Restaurantes
            <select value={size} onChange={(change) => setSize(Number(change.target.value))}>
              {SIZES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={retrain} onChange={(change) => setRetrain(change.target.checked)} />
            Pedir um treino no final
          </label>
          <button className="button" disabled={!category || run.state === "sending"}>Simular interações</button>
        </form>
        <div className="simulation-status" aria-live="polite">
          {run.state === "sending" && <p className="step">Publicando as interações no Kafka…</p>}
          {run.state === "failed" && <p className="step step-error">{run.message}</p>}
          {run.state === "sent" && <SimulationSteps run={run} />}
        </div>
      </div>
    </details>
  );
}

const TRAINING_STEP: Record<Training, string> = {
  off: "Nenhum treino pedido: a lista abaixo muda no próximo treino automático.",
  requested: "Treino pedido. A lista abaixo muda quando o modelo novo entrar em uso.",
  failed: "O treino não foi pedido porque o Kafka não respondeu.",
  done: "Modelo novo em uso: a lista abaixo já considera a simulação.",
};

function SimulationSteps({ run }: { run: Extract<Run, { state: "sent" }> }) {
  const { result, confirmed, training } = run;
  const total = result.event_ids.length;
  const trainingClass = training === "done" ? "step step-ok" : training === "failed" ? "step step-error" : "step";
  return (
    <>
      <ol className="simulation-steps">
        <li className="step step-ok">
          {plural(total, "interação gravada", "interações gravadas")} no Kafka, em{" "}
          {plural(result.restaurants.length, "restaurante", "restaurantes")} de {result.category}
          {result.skipped_views > 0 && ` (${plural(result.skipped_views, "visualização repetida ficou", "visualizações repetidas ficaram")} de fora)`}.
        </li>
        <li className={confirmed === total ? "step step-ok" : "step"}>
          {formatInteger(confirmed)} de {formatInteger(total)} confirmadas pelo backend.
        </li>
        <li className={trainingClass}>
          {TRAINING_STEP[training]}
          {(training === "requested" || training === "failed") && <> <Link to="/painel">Acompanhe no painel</Link>.</>}
        </li>
      </ol>
      <p className="step">
        Restaurantes:{" "}
        {result.restaurants.map((restaurant, index) => (
          <span key={restaurant.id}>
            {index > 0 && ", "}
            <Link to={`/restaurantes/${restaurant.id}`}>{restaurant.name}</Link>
          </span>
        ))}
        .
      </p>
    </>
  );
}
