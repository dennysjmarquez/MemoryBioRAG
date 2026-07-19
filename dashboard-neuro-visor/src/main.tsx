import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Theme } from "@radix-ui/themes";
import App from "./App";
import "@radix-ui/themes/styles.css";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Theme appearance="dark" accentColor="iris" radius="medium" scaling="100%">
        <App />
      </Theme>
    </BrowserRouter>
  </StrictMode>,
);
