<template>
	<FrappeUIProvider>
		<router-view />
		<!-- Mounted once, app-wide: Cmd+K palette, "?" shortcuts help, settings modal. -->
		<AppCommandPalette />
		<ShortcutsHelp />
		<SettingsModal />
	</FrappeUIProvider>
</template>

<script setup>
import { FrappeUIProvider } from "frappe-ui";
import AppCommandPalette from "@/components/AppCommandPalette.vue";
import SettingsModal from "@/components/SettingsModal.vue";
import ShortcutsHelp from "@/components/ShortcutsHelp.vue";
</script>
