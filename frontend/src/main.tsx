import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./presentation/theme/ThemeProvider";
import { BrowserRouter } from "react-router-dom";
import "./presentation/theme/tokens/primitives.css";
import "./presentation/theme/tokens/semantic.css";
import "./presentation/theme/tokens/semantic.dark.css";
import "./index.css";

const container = document.getElementById("root");
if (container) {
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <ThemeProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </React.StrictMode>,
  );
}
