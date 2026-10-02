import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { api, errorMessage, type Category, type Restaurant } from "../api";
import { cuisineShortcuts } from "../categories";
import { Icon } from "../components/Icon";
import { RestaurantCard } from "../components/RestaurantCard";
import { plural } from "../format";

const PAGE = 24;

export function Explore() {
  // The category lives in the URL, so a category chip anywhere in the app opens the filtered catalogue.
  const [params, setParams] = useSearchParams();
  const category = params.get("categoria") ?? "";
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("popular");
  const [categories, setCategories] = useState<Category[]>([]);
  const [page, setPage] = useState<{ total: number; items: Restaurant[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // "Show more" only applies to the filter it was pressed on; any filter change starts from the first page.
  const filter = `${query}|${category}|${sort}`;
  const [more, setMore] = useState({ filter, offset: 0 });
  const offset = more.filter === filter ? more.offset : 0;
  const shortcuts = useMemo(() => cuisineShortcuts(categories), [categories]);

  useEffect(() => {
    api.categories().then(setCategories, () => setCategories([]));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let current = true;
    api.restaurants({ q: query, category, sort, limit: PAGE, offset }).then((value) => {
      if (!current) return;
      setPage((previous) => (offset === 0 || !previous ? value : { total: value.total, items: [...previous.items, ...value.items] }));
      setError(null);
    }, (reason) => current && setError(errorMessage(reason)));
    return () => {
      current = false;
    };
  }, [query, category, sort, offset]);

  function chooseCategory(name: string) {
    setParams(name ? { categoria: name } : {});
  }

  return (
    <main className="page">
      <header className="page-head">
        <h1>Explorar</h1>
        <p className="lede">Os 300 restaurantes da amostra do Yelp em Filadélfia. Abrir um restaurante já conta como visualização.</p>
      </header>

      <ul className="chip-bar" aria-label="Tipos de lugar">
        <li>
          <button type="button" className="chip" aria-pressed={!category} onClick={() => chooseCategory("")}>
            <Icon name="plate" size={18} /> Todos
          </button>
        </li>
        {shortcuts.map((item) => (
          <li key={item.name}>
            <button type="button" className="chip" aria-pressed={category === item.name} onClick={() => chooseCategory(item.name)}>
              <Icon name={item.icon} size={18} /> {item.name} <span className="chip-count">{item.count}</span>
            </button>
          </li>
        ))}
      </ul>

      <div className="filters">
        <label>
          Buscar
          <input type="search" value={search} placeholder="Nome ou categoria" onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label>
          Todas as categorias
          <select value={category} onChange={(event) => chooseCategory(event.target.value)}>
            <option value="">Qualquer uma</option>
            {categories.map((item) => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}
          </select>
        </label>
        <label>
          Ordenar por
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="popular">Mais avaliados no Yelp</option>
            <option value="stars">Melhor nota no Yelp</option>
            <option value="name">Nome</option>
          </select>
        </label>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {page && <p className="quiet result-count">{plural(page.total, "restaurante", "restaurantes")}{category && ` em ${category}`}</p>}
      {page && page.total === 0 && <p className="empty">Nenhum restaurante com esse filtro. Tente outra categoria ou limpe a busca.</p>}
      {page && (
        <ul className="card-grid">
          {page.items.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} />)}
        </ul>
      )}
      {page && page.items.length < page.total && (
        <button className="button button-quiet" onClick={() => setMore({ filter, offset: page.items.length })}>Mostrar mais</button>
      )}
    </main>
  );
}
