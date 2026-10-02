import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { api, errorMessage, type Profile } from "../api";
import { useSession } from "../session";

export function Login() {
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [filter, setFilter] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.profiles().then(setProfiles, (reason) => setError(errorMessage(reason)));
  }, []);

  async function enter(userId: string) {
    setBusy(true);
    setError(null);
    try {
      await signIn(userId);
      navigate("/");
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const profile = await api.createProfile(name.trim());
      await enter(profile.id);
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  }

  const created = profiles?.filter((profile) => profile.origin === "app") ?? [];
  const yelp = profiles?.filter((profile) => profile.origin === "yelp" && profile.display_name.includes(filter.trim())) ?? [];

  return (
    <main className="page login">
      <section className="login-intro">
        <h1>Escolha um perfil</h1>
        <p className="lede">
          Os perfis do Yelp já têm histórico em restaurantes de Filadélfia, então o modelo sabe o que recomendar para eles.
          Um perfil novo começa sem histórico e ganha recomendações próprias no treino seguinte às primeiras interações.
        </p>
        <form className="new-profile" onSubmit={create}>
          <label htmlFor="new-profile-name">Criar um perfil novo</label>
          <div className="inline-form">
            <input id="new-profile-name" value={name} maxLength={40} autoComplete="off" placeholder="Seu nome"
              onChange={(event) => setName(event.target.value)} />
            <button className="button" disabled={busy || !name.trim()}>Criar perfil</button>
          </div>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
        {created.length > 0 && (
          <>
            <h2>Perfis criados no app</h2>
            <ul className="profile-grid">
              {created.map((profile) => (
                <li key={profile.id}>
                  <button className="profile-button" disabled={busy} onClick={() => enter(profile.id)}>{profile.display_name}</button>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="login-profiles" aria-labelledby="yelp-profiles">
        <div className="section-head">
          <h2 id="yelp-profiles">Perfis do Yelp</h2>
          <label className="visually-hidden" htmlFor="profile-filter">Filtrar perfis pelo número</label>
          <input id="profile-filter" type="search" inputMode="numeric" placeholder="Número do perfil" value={filter}
            onChange={(event) => setFilter(event.target.value)} />
        </div>
        {profiles === null && !error && <p className="quiet">Carregando perfis…</p>}
        <ul className="profile-grid">
          {yelp.map((profile) => (
            <li key={profile.id}>
              <button className="profile-button" disabled={busy} onClick={() => enter(profile.id)}>
                {profile.display_name.replace("Perfil Yelp ", "")}
                <span className="visually-hidden"> ({profile.display_name})</span>
              </button>
            </li>
          ))}
        </ul>
        {profiles !== null && yelp.length === 0 && <p className="quiet">Nenhum perfil com esse número.</p>}
      </section>
    </main>
  );
}
