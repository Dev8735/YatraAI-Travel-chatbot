"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";

interface HealthState { health: Health | null; error: string | null }

const HealthContext = createContext<HealthState>({ health: null, error: null });

export function HealthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<HealthState>({ health: null, error: null });
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api<Health>("/health")
        .then((health) => !cancelled && setState({ health, error: null }))
        .catch((e: Error) => !cancelled && setState({ health: null, error: e.message }));
    load();
    const t = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);
  return <HealthContext.Provider value={state}>{children}</HealthContext.Provider>;
}

export function useHealth(): HealthState {
  return useContext(HealthContext);
}
