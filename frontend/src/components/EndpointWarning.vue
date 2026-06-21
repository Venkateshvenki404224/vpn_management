<template>
	<Alert
		v-if="!session.endpointReady"
		theme="yellow"
		title="VPN endpoint not configured"
		description="The public endpoint host hasn't been set, so configuration downloads are unavailable. Contact your administrator."
		class="mb-4"
	/>
</template>

<script setup>
import { Alert } from "frappe-ui";
import { session } from "@/data/session";
</script>
