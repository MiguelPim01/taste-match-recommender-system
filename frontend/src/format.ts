const integer = new Intl.NumberFormat("pt-BR");
const oneDecimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const metric = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const clock = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const shortClock = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const day = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" });

export const formatInteger = (value: number) => integer.format(value);
export const formatStars = (value: number) => oneDecimal.format(value);
export const formatMetric = (value: number) => metric.format(value);
export const formatClock = (iso: string) => clock.format(new Date(iso));
export const formatShortClock = (iso: string) => shortClock.format(new Date(iso));

/** Today's events show the time; the Yelp history shows the date it happened. */
export function formatWhen(iso: string): string {
  const moment = new Date(iso);
  return moment.toDateString() === new Date().toDateString() ? `hoje às ${shortClock.format(moment)}` : day.format(moment);
}

export const INTERACTION_LABEL: Record<string, string> = {
  "restaurant.viewed": "Visualização",
  "restaurant.commented": "Comentário",
  "restaurant.rated": "Avaliação",
};

export const ICON_OF_TYPE: Record<string, "view" | "comment" | "rating"> = {
  "restaurant.viewed": "view",
  "restaurant.commented": "comment",
  "restaurant.rated": "rating",
};

export const SIGNAL_OF_TYPE: Record<string, "views" | "comments" | "reviews"> = {
  "restaurant.viewed": "views",
  "restaurant.commented": "comments",
  "restaurant.rated": "reviews",
};

export const REQUEST_SOURCE: Record<string, string> = {
  "sqlite-monitor": "Monitor, ao somar os eventos novos",
  backend: "Atalho do painel",
  cli: "Linha de comando do treino",
};

export function plural(count: number, one: string, many: string): string {
  return `${formatInteger(count)} ${count === 1 ? one : many}`;
}
