import "@/styles.css";
import "@/app.css";

import App from "@/App";
import { applyTheme, readMode, resolve } from "@/theme";

const { ReactDOM } = (window as unknown as { shinyreact: { ReactDOM: typeof import("react-dom/client") } }).shinyreact;

document.title = "Raw → Ready · Health Data Lab";
applyTheme(resolve(readMode())); // before first paint, so there is no flash of the wrong theme

// The page has no mount container; the client appends its own.
const root = ReactDOM.createRoot(document.body.appendChild(document.createElement("div")));
root.render(<App />);
