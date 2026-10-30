import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";
import { initTheme } from "./theme";
import { reloadOnce } from "./chunkError";
import { watchErrors } from "./clientLog";

initTheme();
watchErrors();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(<React.StrictMode><App /></React.StrictMode>);

// The installed phone app (served over https by the private network) keeps its own files for a quick start. Not in the laptop window.
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('/sw.js').catch(() => {});

// Vite tells us when a lazily loaded file is gone (the app was rebuilt while this window stayed open): reload once to get the new version.
window.addEventListener('vite:preloadError', () => { reloadOnce(); });   // (the error still reaches the page's safety net, so it can explain)
