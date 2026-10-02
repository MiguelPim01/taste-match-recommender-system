import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, type Profile } from "./api";

interface Session {
  profile: Profile | null;
  loading: boolean;
  signIn: (userId: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.session().then(setProfile, () => setProfile(null)).finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (userId: string) => setProfile(await api.startSession(userId)), []);
  const signOut = useCallback(async () => {
    await api.endSession();
    setProfile(null);
  }, []);

  const value = useMemo(() => ({ profile, loading, signIn, signOut }), [profile, loading, signIn, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession precisa de SessionProvider");
  return session;
}
