import type { ReactNode } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from "react-router";

import { ConfirmationTickets } from "./components/Tickets";
import { LiveProvider, useLive } from "./live";
import { Activity } from "./pages/Activity";
import { Dashboard } from "./pages/Dashboard";
import { Explore } from "./pages/Explore";
import { ForYou } from "./pages/ForYou";
import { Login } from "./pages/Login";
import { RestaurantPage } from "./pages/RestaurantPage";
import { useSession } from "./session";

function TopBar() {
  const { profile, signOut } = useSession();
  const { connected } = useLive();
  const navigate = useNavigate();

  async function switchProfile() {
    await signOut();
    navigate("/entrar");
  }

  return (
    <header className="topbar">
      <Link to="/" className="wordmark">TasteMatch</Link>
      <nav className="nav" aria-label="Principal">
        <NavLink to="/" end>Para você</NavLink>
        <NavLink to="/explorar">Explorar</NavLink>
        <NavLink to="/atividade">Minha atividade</NavLink>
        <NavLink to="/painel">Painel</NavLink>
      </nav>
      <div className="topbar-side">
        <span className={connected ? "live live-on" : "live"} title="Conexão em tempo real com o backend">
          {connected ? "Ao vivo" : "Reconectando"}
        </span>
        {profile ? (
          <>
            <span className="profile-name">{profile.display_name}</span>
            <button type="button" className="link-button" onClick={switchProfile}>Trocar perfil</button>
          </>
        ) : <NavLink to="/entrar">Entrar</NavLink>}
      </div>
    </header>
  );
}

function RequireProfile({ children }: { children: ReactNode }) {
  const { profile } = useSession();
  return profile ? children : <Navigate to="/entrar" replace />;
}

export function App() {
  const { profile, loading } = useSession();
  if (loading) return <main className="page"><p className="quiet">Carregando…</p></main>;

  return (
    <LiveProvider profileId={profile?.id ?? null}>
      <TopBar />
      <Routes>
        <Route path="/entrar" element={<Login />} />
        <Route path="/painel" element={<Dashboard />} />
        <Route path="/" element={<RequireProfile><ForYou /></RequireProfile>} />
        <Route path="/explorar" element={<RequireProfile><Explore /></RequireProfile>} />
        <Route path="/restaurantes/:id" element={<RequireProfile><RestaurantPage /></RequireProfile>} />
        <Route path="/atividade" element={<RequireProfile><Activity /></RequireProfile>} />
        <Route path="*" element={<main className="page"><h1>Página não encontrada</h1><p><Link to="/">Voltar para o início</Link></p></main>} />
      </Routes>
      {profile && <ConfirmationTickets />}
    </LiveProvider>
  );
}
