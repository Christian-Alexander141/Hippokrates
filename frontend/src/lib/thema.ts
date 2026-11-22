import { useEffect, useState } from "react";

export type Thema = "system" | "hell" | "dunkel";
const SCHLUESSEL = "hippokrates-thema";

function lesen(): Thema {
  try {
    const w = localStorage.getItem(SCHLUESSEL);
    return w === "hell" || w === "dunkel" ? w : "system";
  } catch {
    return "system";
  }
}

function anwenden(t: Thema) {
  const html = document.documentElement;
  if (t === "system") html.removeAttribute("data-theme");
  else html.setAttribute("data-theme", t === "dunkel" ? "dark" : "light");
}

anwenden(lesen());

/** Farbschema: folgt dem System, lässt sich aber dauerhaft auf hell oder dunkel festlegen. */
export function useThema(): [Thema, () => void] {
  const [thema, setThema] = useState<Thema>(lesen);
  useEffect(() => {
    anwenden(thema);
    try {
      localStorage.setItem(SCHLUESSEL, thema);
    } catch {
      /* privater Modus */
    }
  }, [thema]);
  const weiter = () => setThema((t) => (t === "system" ? "hell" : t === "hell" ? "dunkel" : "system"));
  return [thema, weiter];
}
