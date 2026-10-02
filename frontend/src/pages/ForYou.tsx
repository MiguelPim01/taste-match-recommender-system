import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import { api, errorMessage, type Recommendations } from "../api";
import { RankedRestaurant } from "../components/RestaurantCard";
import { SimulationPanel } from "../components/Simulation";
import { formatShortClock } from "../format";
import { useLiveEvent, useLiveRefresh } from "../live";

function explain(list: Recommendations): string {
  if (list.source === "popular") {
    return "O modelo ainda não conhece este perfil, então estes são os mais bem avaliados agora. "
      + "Abra restaurantes, avalie e comente: a lista passa a ser sua no próximo treino.";
  }
  const when = list.model ? ` às ${formatShortClock(list.model.generated_at)}` : "";
  if (list.source === "mixed") {
    return `Os primeiros vêm do modelo que entrou em uso${when}; os outros são os mais bem avaliados agora, para completar a lista.`;
  }
  return `Escolhidos pelo modelo que entrou em uso${when}, a partir do que você e os outros perfis fizeram. `
    + "Restaurantes que você já abriu ficam de fora.";
}

export function ForYou() {
  const [list, setList] = useState<Recommendations | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api.recommendations(12).then((value) => {
      setList(value);
      setError(null);
    }, (reason) => setError(errorMessage(reason)));
  }, []);

  useEffect(load, [load]);
  useLiveEvent("ready", load);
  // What you just opened, rated or commented leaves the list right away, without waiting for a new model.
  useLiveRefresh("interaction.recorded", load);
  useLiveEvent("recommendations.updated", () => {
    setNotice("O modelo novo chegou e sua lista foi recalculada.");
    load();
  });

  return (
    <main className="page">
      <header className="page-head">
        <h1>Para você</h1>
        {list && <p className="lede">{explain(list)}</p>}
        <SimulationPanel />
      </header>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {list && list.items.length === 0 && (
        <p className="empty">Não há recomendações agora. <Link to="/explorar">Explore o catálogo</Link> para começar.</p>
      )}
      {list && (
        <ol className="board">
          {list.items.map((item, index) => (
            <RankedRestaurant key={item.restaurant.id} restaurant={item.restaurant} rank={index + 1} source={item.source}
              showSource={list.source === "mixed"} />
          ))}
        </ol>
      )}
    </main>
  );
}
