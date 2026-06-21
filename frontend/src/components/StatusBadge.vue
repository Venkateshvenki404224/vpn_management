<template>
	<Badge :theme="theme" :label="status || 'Unknown'" variant="subtle" />
</template>

<script setup>
import { Badge } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	status: { type: String, default: "" },
});

// Peer/server status → frappe-ui Badge theme.
const THEMES = {
	Active: "green",
	Provisioned: "green",
	Up: "green",
	Pending: "blue",
	Stale: "orange",
	Revoked: "red",
	Error: "red",
	Down: "gray",
	Disabled: "gray",
};

const theme = computed(() => THEMES[props.status] || "gray");
</script>
