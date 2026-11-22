export class ApiFehler extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** Fetch-Hülle: JSON hin und zurück, FastAPI-Fehlermeldungen als lesbarer Text. */
export async function api<T>(pfad: string, methode = "GET", daten?: unknown): Promise<T> {
  const optionen: RequestInit = { method: methode };
  if (daten instanceof Blob) optionen.body = daten;
  else if (daten !== undefined) {
    optionen.body = JSON.stringify(daten);
    optionen.headers = { "Content-Type": "application/json" };
  }
  let antwort: Response;
  try {
    antwort = await fetch(pfad, optionen);
  } catch {
    throw new ApiFehler("Server nicht erreichbar – läuft Hippokrates noch?", 0);
  }
  if (!antwort.ok) {
    let text = `Fehler ${antwort.status}`;
    try {
      const j = await antwort.json();
      text = typeof j.detail === "string"
        ? j.detail
        : (j.detail as { loc: string[]; msg: string }[]).map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ");
    } catch {
      /* keine JSON-Antwort */
    }
    throw new ApiFehler(text, antwort.status);
  }
  return antwort.json() as Promise<T>;
}
