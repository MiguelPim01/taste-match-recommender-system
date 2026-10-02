// Types mirror the FastAPI responses (backend/src/tastematch_api/routes).

export type Origin = "yelp" | "app";
export type Signal = "views" | "comments" | "reviews";

export interface Profile {
  id: string;
  display_name: string;
  origin: Origin;
}

export interface Restaurant {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  stars: number | null;
  review_count: number;
  categories: string[];
  rating_average: number | null;
  rating_count: number;
  views_last_hour: number;
}

export interface RestaurantComment {
  user_id: string;
  display_name: string | null;
  text: string;
  occurred_at: string;
}

export interface RestaurantDetail extends Restaurant {
  recent_comments: RestaurantComment[];
  my_rating: number | null;
}

export interface Category {
  name: string;
  count: number;
}

export interface Accepted {
  status: "published" | "skipped";
  event_id: string | null;
  type: string;
  topic: string;
  partition: number | null;
  offset: number | null;
}

export interface HistoryItem {
  event_id: string;
  type: string;
  restaurant_id: string;
  restaurant_name: string | null;
  stars: number | null;
  text: string | null;
  occurred_at: string;
}

export interface Recommendations {
  source: "model" | "mixed" | "popular";
  model: { run_id: string; generated_at: string } | null;
  items: { source: "model" | "popular"; restaurant: Restaurant }[];
}

export interface CategoryActivity extends Record<Signal, number> {
  category: string;
  total: number;
}

export interface Simulation {
  category: string;
  restaurants: { id: string; name: string }[];
  event_ids: string[];
  skipped_views: number;
}

export interface MinuteCount extends Record<Signal, number> {
  minute: string;
}

export interface ModelVersion {
  run_id: string;
  metric_name: string;
  metric_value: number;
  trained_until_total: number;
  created_at: string;
}

export interface RetrainRequest {
  event_id: string;
  requested_at: string;
  source: string | null;
  force: boolean;
  observed_total: number | null;
}

export interface Dashboard {
  totals: Record<Signal, number>;
  events_per_minute: MinuteCount[];
  next_training: { threshold: number; new_events: number; remaining: number };
  current_model: ModelVersion | null;
  models: ModelVersion[];
  retrain_requests: RetrainRequest[];
  request_after_last_model: boolean;
  recent_events: RecentEvent[];
}

export interface RecentEvent {
  event_id: string;
  type: string;
  user_id: string;
  restaurant_id: string;
  occurred_at: string;
  stars: number | null;
  text: string | null;
  recorded_at: string;
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    let message = `A API respondeu ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // keeps the generic message
    }
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Sem resposta da API. Confira se o backend está no ar e tente de novo.";
}

/** Idempotency-Key for one action; a retry of the same action reuses it. Works outside HTTPS too. */
export function newActionKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

const names = new Map<string, string>();

function remember<T extends { id: string; name: string }>(restaurants: T[]): void {
  restaurants.forEach((restaurant) => names.set(restaurant.id, restaurant.name));
}

/** Names for tickets: SSE events carry only the restaurant ID. */
export function restaurantName(id: string): string | undefined {
  return names.get(id);
}

let catalogNames: Promise<void> | null = null;

export function loadCatalogNames(): Promise<void> {
  catalogNames ??= Promise.all([0, 100, 200].map((offset) => api.restaurants({ limit: 100, offset })))
    .then(() => undefined)
    .catch((error) => {
      catalogNames = null;
      throw error;
    });
  return catalogNames;
}

const json = (body: unknown) => JSON.stringify(body);
const keyed = (key: string) => ({ "Idempotency-Key": key });

export const api = {
  session: () => request<Profile>("/api/session"),
  startSession: (userId: string) => request<Profile>("/api/session", { method: "POST", body: json({ user_id: userId }) }),
  endSession: () => request<void>("/api/session", { method: "DELETE" }),
  profiles: () => request<Profile[]>("/api/users"),
  createProfile: (displayName: string) =>
    request<Profile>("/api/users", { method: "POST", body: json({ display_name: displayName }) }),

  async restaurants(params: { q?: string; category?: string; sort?: string; limit?: number; offset?: number }) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const page = await request<{ total: number; items: Restaurant[] }>(`/api/restaurants?${query}`);
    remember(page.items);
    return page;
  },
  categories: () => request<Category[]>("/api/restaurants/categories"),
  async restaurant(id: string) {
    const restaurant = await request<RestaurantDetail>(`/api/restaurants/${encodeURIComponent(id)}`);
    remember([restaurant]);
    return restaurant;
  },

  view: (id: string, key: string) =>
    request<Accepted>(`/api/restaurants/${encodeURIComponent(id)}/views`, { method: "POST", headers: keyed(key) }),
  comment: (id: string, text: string, key: string) =>
    request<Accepted>(`/api/restaurants/${encodeURIComponent(id)}/comments`, {
      method: "POST", headers: keyed(key), body: json({ text }),
    }),
  rate: (id: string, stars: number, key: string) =>
    request<Accepted>(`/api/restaurants/${encodeURIComponent(id)}/rating`, {
      method: "PUT", headers: keyed(key), body: json({ stars }),
    }),

  history: () => request<HistoryItem[]>("/api/me/history?limit=100"),
  categoryActivity: () => request<CategoryActivity[]>("/api/me/categories"),
  simulate: (category: string, restaurants: number) =>
    request<Simulation>("/api/me/simulate", { method: "POST", body: json({ category, restaurants }) }),
  async recommendations(limit = 12) {
    const list = await request<Recommendations>(`/api/me/recommendations?limit=${limit}`);
    remember(list.items.map((item) => item.restaurant));
    return list;
  },

  dashboard: () => request<Dashboard>("/api/dashboard"),
  retrain: (key: string) =>
    request<{ event_id: string }>("/api/admin/retrain", { method: "POST", headers: keyed(key) }),
};
