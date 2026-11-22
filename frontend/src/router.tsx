import { createBrowserRouter, Navigate } from "react-router";
import { AppRahmen } from "./components/layout/AppRahmen";
import { Admin } from "./views/Admin";
import { Technik } from "./views/Technik";
import { Uebersicht } from "./views/Uebersicht";
import { Akte } from "./views/patienten/Akte";
import { Diagnose } from "./views/patienten/diagnose/Diagnose";
import { PatientKopf } from "./views/patienten/PatientKopf";
import { KeinPatient, PatientenRahmen } from "./views/patienten/PatientenRahmen";

export const router = createBrowserRouter([
  {
    element: <AppRahmen />,
    children: [
      { path: "/", element: <main className="haupt"><Uebersicht /></main> },
      {
        path: "/patienten",
        element: <PatientenRahmen />,
        children: [
          { index: true, element: <KeinPatient /> },
          { path: "neu", element: <Akte /> },
          {
            path: ":id",
            element: <PatientKopf />,
            children: [
              { index: true, element: <Navigate to="diagnose" replace /> },
              { path: "diagnose", element: <Diagnose /> },
              { path: "akte", element: <Akte /> },
            ],
          },
        ],
      },
      { path: "/admin", element: <main className="haupt"><Admin /></main> },
      { path: "/technik", element: <main className="haupt"><Technik /></main> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
