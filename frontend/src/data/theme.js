import { reactive } from "vue";

// Light/dark choice, persisted (namespaced like `vpn_sidebar_collapsed`). The
// espresso tokens flip under `[data-theme="dark"]` on <html> — frappe-ui ships
// the dark token values — so toggling the attribute restyles the whole app.
const STORAGE_KEY = "vpn_theme";

export const theme = reactive({
	dark: localStorage.getItem(STORAGE_KEY) === "dark",
});

function apply() {
	document.documentElement.setAttribute("data-theme", theme.dark ? "dark" : "light");
}

export function toggleTheme() {
	theme.dark = !theme.dark;
	localStorage.setItem(STORAGE_KEY, theme.dark ? "dark" : "light");
	apply();
}

// Apply the saved theme as soon as this module loads (imported from main.js),
// so the attribute is set before first paint and there is no light-mode flash.
apply();
