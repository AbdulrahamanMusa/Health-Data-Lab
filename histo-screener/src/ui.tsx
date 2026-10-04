import "@/styles.css";

import App from "@/App";
import { applyTheme, readMode, resolve } from "@/theme";

const { ReactDOM } = (window as unknown as { shinyreact: { ReactDOM: typeof import("react-dom/client") } }).shinyreact;

document.title = "Histopathology Screener · Health Data Lab";
applyTheme(resolve(readMode())); // before first paint: no flash of the wrong theme

// The page has no mount container; the client appends its own.
const mount = Object.assign(document.createElement("div"), { id: "app-root" });
const root = ReactDOM.createRoot(document.body.appendChild(mount));
root.render(<App />);
