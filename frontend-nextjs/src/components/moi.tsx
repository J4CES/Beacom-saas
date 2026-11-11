"use client";

import { createContext, useContext } from "react";

import type { Moi } from "@/lib/types";

export const ContexteMoi = createContext<Moi | null>(null);

/** Utilisateur connecté (rôle, organisation, plan), chargé une fois pour tout l'espace client. */
export function useMoi(): Moi {
  const moi = useContext(ContexteMoi);
  if (!moi) throw new Error("useMoi hors de l'espace client");
  return moi;
}
