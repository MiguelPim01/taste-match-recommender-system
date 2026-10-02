import { useEffect, useState } from "react";

import { loadCatalogNames, restaurantName } from "../api";
import { ICON_OF_TYPE, INTERACTION_LABEL, SIGNAL_OF_TYPE, formatClock } from "../format";
import { useLiveEvent, type InteractionSummary } from "../live";
import { Icon } from "./Icon";

// Each interaction is printed like a kitchen order ticket: the event that reached Kafka, on paper.

export interface TicketData extends InteractionSummary {
  received_at: string;
}

function detail(ticket: InteractionSummary): string {
  if (ticket.stars !== null) return `nota ${ticket.stars} de 5`;
  if (ticket.text) return `“${ticket.text.length > 60 ? `${ticket.text.slice(0, 60)}…` : ticket.text}”`;
  return "abriu a página";
}

export function Ticket({ ticket, confirmed }: { ticket: TicketData; confirmed?: boolean }) {
  return (
    <article className={`ticket ticket-${SIGNAL_OF_TYPE[ticket.type] ?? "views"}`}>
      <p className="ticket-type"><Icon name={ICON_OF_TYPE[ticket.type] ?? "view"} size={15} /> {INTERACTION_LABEL[ticket.type] ?? ticket.type}</p>
      <p className="ticket-place">{restaurantName(ticket.restaurant_id) ?? ticket.restaurant_id}</p>
      <p className="ticket-detail">{detail(ticket)}</p>
      <p className="ticket-time">
        <span>{formatClock(ticket.received_at)}</span>
        {confirmed && <span className="ticket-check">confirmado</span>}
      </p>
    </article>
  );
}

/** The kitchen rail of the dashboard: newest ticket on the left, the rest pushed along. */
export function TicketRail({ tickets }: { tickets: TicketData[] }) {
  useNames();
  if (tickets.length === 0) {
    return <p className="rail-empty">Nenhum evento nos últimos minutos. Quando alguém ver, comentar ou avaliar um restaurante, a comanda aparece aqui.</p>;
  }
  return (
    <ol className="rail" aria-label="Eventos mais recentes">
      {tickets.map((ticket) => (
        <li key={ticket.event_id}><Ticket ticket={ticket} /></li>
      ))}
    </ol>
  );
}

/** Your own actions come back from Kafka through the projector; each confirmation prints a ticket. */
export function ConfirmationTickets() {
  const [tickets, setTickets] = useState<TicketData[]>([]);
  useNames();

  useLiveEvent("interaction.recorded", (event) => {
    if (!event.event_id.startsWith("app:")) return;
    const ticket = { ...event, received_at: new Date().toISOString() };
    setTickets((current) => [ticket, ...current.filter((item) => item.event_id !== event.event_id)].slice(0, 3));
    window.setTimeout(() => setTickets((current) => current.filter((item) => item !== ticket)), 7000);
  });

  return (
    <div className="confirmations" role="status" aria-live="polite">
      {tickets.map((ticket) => <Ticket key={ticket.event_id} ticket={ticket} confirmed />)}
    </div>
  );
}

function useNames(): void {
  const [, setLoaded] = useState(false);
  useEffect(() => {
    loadCatalogNames().then(() => setLoaded(true), () => undefined);
  }, []);
}
