import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./styles/tokens.css";
import "./styles/basis.css";
import "./styles/komponenten.css";
import "./styles/ansichten.css";
import { RueckmeldungProvider } from "./components/rueckmeldung";
import { router } from "./router";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 2_000, refetchOnWindowFocus: true } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RueckmeldungProvider>
        <RouterProvider router={router} />
      </RueckmeldungProvider>
    </QueryClientProvider>
  </StrictMode>,
);
