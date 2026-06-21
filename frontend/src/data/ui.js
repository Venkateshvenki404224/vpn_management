import { reactive } from "vue";

// Shell-level overlay state shared between the sidebar header dropdown (which
// triggers them) and App.vue (which mounts them once, app-wide). Namespaced like
// the other small reactive stores (`theme`, session). No new dependency.
export const ui = reactive({
	paletteOpen: false,
	shortcutsOpen: false,
	settingsOpen: false,
});

export function openPalette() {
	ui.paletteOpen = true;
}

export function openShortcuts() {
	ui.shortcutsOpen = true;
}

export function openSettings() {
	ui.settingsOpen = true;
}
