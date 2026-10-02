import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import { api, errorMessage, type CategoryActivity, type HistoryItem } from "../api";
import { CategoryChart } from "../components/CategoryChart";
import { Icon } from "../components/Icon";
import { StarRow } from "../components/Stars";
import { ICON_OF_TYPE, INTERACTION_LABEL, SIGNAL_OF_TYPE, formatWhen } from "../format";
import { useLiveRefresh } from "../live";

export function Activity() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [categories, setCategories] = useState<CategoryActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.history(), api.categoryActivity()]).then(([history, activity]) => {
      setItems(history);
      setCategories(activity);
      setError(null);
    }, (reason) => setError(errorMessage(reason)));
  }, []);

  useEffect(load, [load]);
  useLiveRefresh("interaction.recorded", load);

  return (
    <main className="page">
      <header className="page-head">
        <h1>Minha atividade</h1>
        <p className="lede">O que este perfil fez. Cada interação é um evento que passou pelo Kafka.</p>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {items?.length === 0 && (
        <p className="empty">Nenhuma interação ainda. <Link to="/explorar">Abra um restaurante</Link> para começar.</p>
      )}
      {categories && categories.length > 0 && (
        <section className="activity-section" aria-labelledby="activity-categories">
          <div className="section-head">
            <h2 id="activity-categories">Categorias nas suas interações</h2>
            <p className="quiet">Cada interação conta para todas as categorias do restaurante.</p>
          </div>
          <CategoryChart rows={categories} />
        </section>
      )}
      {items && items.length > 0 && (
        <section aria-labelledby="activity-history">
          <div className="section-head">
            <h2 id="activity-history">Histórico</h2>
            <p className="quiet">
              {items.length === 100 ? "As 100 mais recentes, da mais nova para a mais antiga." : "Da mais recente para a mais antiga."}
            </p>
          </div>
          <ol className="timeline">
            {items.map((item) => (
              <li key={`${item.type}-${item.event_id}`} className={`timeline-item timeline-${SIGNAL_OF_TYPE[item.type] ?? "views"}`}>
                <span className="timeline-type"><Icon name={ICON_OF_TYPE[item.type] ?? "view"} size={16} /> {INTERACTION_LABEL[item.type] ?? item.type}</span>
                <Link className="timeline-place" to={`/restaurantes/${item.restaurant_id}`}>{item.restaurant_name ?? item.restaurant_id}</Link>
                <span className="timeline-detail">
                  {item.stars !== null && <StarRow value={item.stars} size={14} />}
                  {item.text && <span className="quiet">“{item.text.length > 140 ? `${item.text.slice(0, 140)}…` : item.text}”</span>}
                </span>
                <time dateTime={item.occurred_at}>{formatWhen(item.occurred_at)}</time>
              </li>
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
