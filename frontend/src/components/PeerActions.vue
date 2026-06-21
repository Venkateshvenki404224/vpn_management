<template>
	<div class="flex items-center justify-end gap-2">
		<Button
			label="Download .conf"
			icon-left="lucide-download"
			:disabled="!session.endpointReady"
			@click="downloadConf"
		/>
		<Button
			label="QR"
			icon-left="lucide-qr-code"
			:disabled="!session.endpointReady"
			@click="emit('show-qr', peer)"
		/>
	</div>
</template>

<script setup>
import { Button } from "frappe-ui";
import { session } from "@/data/session";

const props = defineProps({
	peer: { type: Object, required: true },
});
const emit = defineEmits(["show-qr"]);

// Same-origin GET download; the session cookie authenticates the stream.
function downloadConf() {
	window.location = `/api/method/vpn_management.api.my_config_download?name=${encodeURIComponent(
		props.peer.name
	)}`;
}
</script>
