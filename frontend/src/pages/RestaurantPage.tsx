import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";

import { api, errorMessage, newActionKey, type Accepted, type RestaurantComment, type RestaurantDetail } from "../api";
import { CategoryChips, Emblem } from "../components/Categories";
import { RestaurantFacts } from "../components/RestaurantCard";
import { StarInput } from "../components/Stars";
import { formatClock, formatWhen } from "../format";
import { useLiveEvent } from "../live";

// An action is "waiting" once Kafka acknowledged it (HTTP 202) and "confirmed" when the backend projector
// reads it back from the topic and the SSE stream says so.
type Step =
  | { state: "idle" }
  | { state: "sending" }
  | { state: "waiting"; eventId: string }
  | { state: "confirmed"; at: string }
  | { state: "failed"; message: string; retry: () => void };

const IDLE: Step = { state: "idle" };

function StepStatus({ step, done }: { step: Step; done: string }) {
  switch (step.state) {
    case "sending":
      return <p className="step" role="status">Enviando para o Kafka…</p>;
    case "waiting":
      return <p className="step" role="status">Gravado no Kafka. Esperando a confirmação…</p>;
    case "confirmed":
      return <p className="step step-ok" role="status">{done} às {formatClock(step.at)}.</p>;
    case "failed":
      return (
        <p className="step step-error" role="alert">
          {step.message} <button type="button" className="link-button" onClick={step.retry}>Tentar de novo</button>
        </p>
      );
    default:
      return null;
  }
}

function Comment({ comment }: { comment: RestaurantComment }) {
  const [open, setOpen] = useState(false);
  const long = comment.text.length > 320;
  return (
    <li className="comment">
      <p className="comment-meta">
        <strong>{comment.display_name ?? "Perfil sem nome"}</strong> <span className="quiet">{formatWhen(comment.occurred_at)}</span>
      </p>
      <p className="comment-text">{long && !open ? `${comment.text.slice(0, 320).trimEnd()}…` : comment.text}</p>
      {long && (
        <button type="button" className="link-button" onClick={() => setOpen((value) => !value)}>
          {open ? "Mostrar menos" : "Ler tudo"}
        </button>
      )}
    </li>
  );
}

export function RestaurantPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [restaurant, setRestaurant] = useState<RestaurantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rating, setRating] = useState<Step>(IDLE);
  const [chosen, setChosen] = useState<number | null>(null);
  const [comment, setComment] = useState<Step>(IDLE);
  const [text, setText] = useState("");
  const confirmed = useRef(new Set<string>());

  const load = useCallback(() => {
    api.restaurant(id).then((value) => {
      setRestaurant(value);
      setError(null);
    }, (reason) => setError(errorMessage(reason)));
  }, [id]);

  useEffect(load, [load]);
  // Opening the page is the view; the backend ignores repeats of the same profile within 30 minutes.
  useEffect(() => {
    api.view(id, newActionKey()).catch(() => undefined);
  }, [id]);

  useLiveEvent("interaction.recorded", (event) => {
    if (event.restaurant_id !== id) return;
    confirmed.current.add(event.event_id);
    const at = new Date().toISOString();
    setRating((step) => (step.state === "waiting" && step.eventId === event.event_id ? { state: "confirmed", at } : step));
    setComment((step) => (step.state === "waiting" && step.eventId === event.event_id ? { state: "confirmed", at } : step));
    load();
  });

  useEffect(() => {
    if (comment.state === "confirmed") setText("");
  }, [comment.state]);

  async function send(action: (key: string) => Promise<Accepted>, setStep: (step: Step) => void, key = newActionKey()) {
    setStep({ state: "sending" });
    try {
      const accepted = await action(key);
      const eventId = accepted.event_id ?? "";
      // The confirmation can beat the HTTP response back; then it is already done.
      setStep(confirmed.current.has(eventId)
        ? { state: "confirmed", at: new Date().toISOString() }
        : { state: "waiting", eventId });
    } catch (reason) {
      setStep({ state: "failed", message: errorMessage(reason), retry: () => send(action, setStep, key) });
    }
  }

  function rate(stars: number) {
    setChosen(stars);
    send((key) => api.rate(id, stars, key), setRating);
  }

  function submitComment(event: FormEvent) {
    event.preventDefault();
    const body = text.trim();
    send((key) => api.comment(id, body, key), setComment);
  }

  if (error && !restaurant) {
    return (
      <main className="page">
        <p className="error" role="alert">{error}</p>
        <button className="button button-quiet" onClick={() => navigate("/explorar")}>Ir para o catálogo</button>
      </main>
    );
  }
  if (!restaurant) return <main className="page"><p className="quiet">Carregando restaurante…</p></main>;

  const place = [restaurant.address, restaurant.city].filter(Boolean).join(", ");
  return (
    <main className="page restaurant">
      <button type="button" className="link-button back" onClick={() => navigate(-1)}>Voltar</button>
      <header className="restaurant-head">
        <div className="restaurant-title">
          <Emblem categories={restaurant.categories} large />
          <h1 className="restaurant-name">{restaurant.name}</h1>
        </div>
        <CategoryChips categories={restaurant.categories} limit={10} />
        {place && <p className="quiet address">{place}</p>}
        <RestaurantFacts restaurant={restaurant} />
      </header>

      <div className="restaurant-grid">
        <section className="panel" aria-labelledby="your-rating">
          <h2 id="your-rating">Sua nota</h2>
          <StarInput value={chosen ?? restaurant.my_rating} onChange={rate} disabled={rating.state === "sending"} />
          <StepStatus step={rating} done="Nota registrada" />

          <form className="comment-form" onSubmit={submitComment}>
            <h2 id="comment-heading">Comentar</h2>
            <textarea id="comment-text" aria-labelledby="comment-heading" rows={4} maxLength={5000} value={text}
              placeholder="O que valeu a visita? O que poderia ser melhor?"
              onChange={(event) => setText(event.target.value)} />
            <button className="button" disabled={!text.trim() || comment.state === "sending"}>Enviar comentário</button>
          </form>
          <StepStatus step={comment} done="Comentário publicado" />
        </section>

        <section aria-labelledby="recent-comments">
          <h2 id="recent-comments">Comentários recentes</h2>
          {restaurant.recent_comments.length === 0
            ? <p className="quiet">Ninguém comentou ainda. O seu pode ser o primeiro.</p>
            : <ul className="comments">{restaurant.recent_comments.map((item) => <Comment key={`${item.user_id}-${item.occurred_at}`} comment={item} />)}</ul>}
        </section>
      </div>
    </main>
  );
}
