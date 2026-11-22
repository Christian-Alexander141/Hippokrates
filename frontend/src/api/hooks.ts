import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AbgleichStand, Bibliothek, Einstellungen, EinstellungenAntwort, ModellListe, NetzUebersicht, Patient,
  PatientDaten, PatientEintrag,
} from "./types";

export const schluessel = {
  patienten: ["patienten"] as const,
  patient: (id: number) => ["patient", id] as const,
  abgleich: (id: number) => ["abgleich", id] as const,
  einstellungen: ["einstellungen"] as const,
  modelle: ["modelle"] as const,
  netze: ["netze"] as const,
  bibliothek: ["bibliothek"] as const,
};

// ── Lesen ──────────────────────────────────────────────────────────────────

export function usePatienten() {
  return useQuery({
    queryKey: schluessel.patienten,
    queryFn: () => api<PatientEintrag[]>("/api/patienten"),
    refetchInterval: (q) => (q.state.data?.some((p) => p.zustand === "laufend") ? 3000 : false),
  });
}

export function usePatient(id: number | null) {
  return useQuery({
    queryKey: schluessel.patient(id ?? 0),
    queryFn: () => api<Patient>(`/api/patienten/${id}`),
    enabled: id !== null,
  });
}

export function useAbgleich(id: number | null) {
  return useQuery({
    queryKey: schluessel.abgleich(id ?? 0),
    queryFn: () => api<AbgleichStand>(`/api/patienten/${id}/abgleich`),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data?.lauf?.status === "laufend" ? 1500 : false),
  });
}

export function useEinstellungen() {
  return useQuery({
    queryKey: schluessel.einstellungen,
    queryFn: () => api<EinstellungenAntwort>("/api/einstellungen"),
  });
}

/** Verfügbare Modelle – das Backend fragt bei jedem Aufruf alle Quellen neu ab. */
export function useModelle() {
  return useQuery({
    queryKey: schluessel.modelle,
    queryFn: () => api<ModellListe>("/api/modelle"),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useNetze() {
  return useQuery({ queryKey: schluessel.netze, queryFn: () => api<NetzUebersicht>("/api/netze") });
}

export function useBibliothek() {
  return useQuery({
    queryKey: schluessel.bibliothek,
    queryFn: () => api<Bibliothek>("/api/bibliothek"),
    refetchInterval: (q) => (q.state.data?.status.laeuft ? 1200 : false),
  });
}

// ── Ändern ─────────────────────────────────────────────────────────────────

export function usePatientSpeichern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, daten }: { id: number | null; daten: PatientDaten }) =>
      api<{ patient: Patient; abgleich_gestartet: boolean }>(
        id ? `/api/patienten/${id}` : "/api/patienten", id ? "PUT" : "POST", daten),
    onSuccess: (r) => {
      qc.setQueryData(schluessel.patient(r.patient.id), r.patient);
      qc.invalidateQueries({ queryKey: schluessel.patienten });
      qc.invalidateQueries({ queryKey: schluessel.abgleich(r.patient.id) });
    },
  });
}

export function usePatientLoeschen() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/api/patienten/${id}`, "DELETE"),
    onSuccess: () => qc.invalidateQueries({ queryKey: schluessel.patienten }),
  });
}

export function useAbgleichStarten() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<{ lauf_id: number }>(`/api/patienten/${id}/abgleich`, "POST"),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: schluessel.abgleich(id) });
      qc.invalidateQueries({ queryKey: schluessel.patienten });
    },
  });
}

export function useAntwortenSenden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, antworten }: { id: number; antworten: { frage: string; antwort: string }[] }) =>
      api(`/api/patienten/${id}/antworten`, "POST", { antworten }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: schluessel.abgleich(id) });
      qc.invalidateQueries({ queryKey: schluessel.patient(id) });
      qc.invalidateQueries({ queryKey: schluessel.patienten });
    },
  });
}

export function useEinstellungenAendern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (werte: Partial<Einstellungen>) =>
      api<{ einstellungen: Einstellungen }>("/api/einstellungen", "PATCH", werte),
    onSuccess: (r) => {
      qc.setQueryData<EinstellungenAntwort>(schluessel.einstellungen, (alt) =>
        alt ? { ...alt, einstellungen: r.einstellungen } : alt);
      qc.invalidateQueries({ queryKey: schluessel.einstellungen });
      qc.invalidateQueries({ queryKey: schluessel.modelle });
      qc.invalidateQueries({ queryKey: schluessel.bibliothek });
    },
  });
}

export function useBibliothekAktion() {
  const qc = useQueryClient();
  const fertig = () => {
    qc.invalidateQueries({ queryKey: schluessel.bibliothek });
    qc.invalidateQueries({ queryKey: schluessel.einstellungen });
  };
  return {
    hochladen: useMutation({
      mutationFn: async (dateien: File[]) => {
        for (const d of dateien) await api(`/api/bibliothek/datei?name=${encodeURIComponent(d.name)}`, "POST", d);
      },
      onSuccess: fertig,
    }),
    loeschen: useMutation({
      mutationFn: (name: string) => api(`/api/bibliothek/datei?name=${encodeURIComponent(name)}`, "DELETE"),
      onSuccess: fertig,
    }),
    indexieren: useMutation({ mutationFn: () => api("/api/bibliothek/indexieren", "POST"), onSuccess: fertig }),
  };
}
