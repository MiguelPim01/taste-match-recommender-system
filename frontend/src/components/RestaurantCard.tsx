import { Link } from "react-router";

import type { Restaurant } from "../api";
import { formatInteger, formatStars, plural } from "../format";
import { CategoryChips, Emblem } from "./Categories";
import { Icon } from "./Icon";
import { StarIcon } from "./Stars";

export function RestaurantFacts({ restaurant }: { restaurant: Restaurant }) {
  return (
    <ul className="facts">
      {restaurant.stars !== null && (
        <li>
          <StarIcon /> <strong>{formatStars(restaurant.stars)}</strong> no Yelp
          <span className="quiet"> ({formatInteger(restaurant.review_count)} avaliações)</span>
        </li>
      )}
      {restaurant.rating_average !== null && (
        <li>
          <strong>{formatStars(restaurant.rating_average)}</strong> no TasteMatch
          <span className="quiet"> ({plural(restaurant.rating_count, "nota", "notas")})</span>
        </li>
      )}
      {restaurant.views_last_hour > 0 && (
        <li><Icon name="view" size={16} /> {plural(restaurant.views_last_hour, "visita", "visitas")} na última hora</li>
      )}
    </ul>
  );
}

const SOURCE_LABEL = { model: "Escolha do modelo", popular: "Popular agora" };

/** A row of the "Para você" board: the rank is real information, so it is printed large. */
export function RankedRestaurant({ restaurant, rank, source, showSource }: {
  restaurant: Restaurant;
  rank: number;
  source: "model" | "popular";
  showSource: boolean;
}) {
  return (
    <li className="ranked">
      <span className="rank" aria-hidden="true">{rank}</span>
      <div className="ranked-body">
        <div className="ranked-title">
          <div className="sign-head">
            <Emblem categories={restaurant.categories} />
            <Link className="sign-name" to={`/restaurantes/${restaurant.id}`}>{restaurant.name}</Link>
          </div>
          {showSource && <span className={`tag tag-${source}`}>{SOURCE_LABEL[source]}</span>}
        </div>
        <CategoryChips categories={restaurant.categories} limit={4} />
        <RestaurantFacts restaurant={restaurant} />
      </div>
    </li>
  );
}

export function RestaurantCard({ restaurant }: { restaurant: Restaurant }) {
  return (
    <li className="card">
      <div className="sign-head">
        <Emblem categories={restaurant.categories} />
        <Link className="sign-name" to={`/restaurantes/${restaurant.id}`}>{restaurant.name}</Link>
      </div>
      <CategoryChips categories={restaurant.categories} limit={3} />
      <RestaurantFacts restaurant={restaurant} />
    </li>
  );
}
