<template>
  <Dialog v-model:open="open" bare size="xl" position="top">
    <template #default>
      <Combobox nullable @update:model-value="onSelect">
        <div class="relative">
          <span
            class="lucide-search pointer-events-none absolute left-4 top-3.5 size-4 text-ink-gray-5"
            aria-hidden="true"
          />
          <ComboboxInput
            class="w-full border-none bg-transparent py-3 pl-11 pr-4 text-base text-ink-gray-8 placeholder-ink-gray-4 focus:ring-0"
            placeholder="Search peers, servers, or actions…"
            autocomplete="off"
            :value="query"
            @input="query = $event.target.value"
          />
        </div>
        <ComboboxOptions static hold class="max-h-96 overflow-auto border-t border-outline-gray-1 p-1.5">
          <div v-for="grp in groups" :key="grp.title" class="mb-1.5 mt-3 first:mt-1">
            <div class="px-2.5 pb-1 text-xs font-medium text-ink-gray-5">{{ grp.title }}</div>
            <ComboboxOption
              v-for="item in grp.items"
              :key="item.name"
              v-slot="{ active }"
              :value="item"
              :disabled="item.disabled"
            >
              <CommandItem :item="item" :active="active" />
            </ComboboxOption>
          </div>
          <div v-if="!groups.length" class="px-3 py-10 text-center text-sm text-ink-gray-5">
            No matches for “{{ query }}”
          </div>
        </ComboboxOptions>
      </Combobox>
    </template>
  </Dialog>
</template>

<script setup>
import {
  Combobox,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
} from "@headlessui/vue";
import { Dialog, createResource } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import CommandItem from "@/components/CommandItem.vue";
import { isAdmin } from "@/data/session";
import { theme, toggleTheme } from "@/data/theme";
import { openSettings, openShortcuts, ui } from "@/data/ui";

const router = useRouter();

// Built on our own Dialog + headlessui Combobox (the Help Desk CP.vue pattern)
// rather than frappe-ui's packaged CommandPalette, so we own open-state, the
// Cmd+K shortcut, and filtering. `open` is the shared store flag the sidebar
// dropdown also flips.
const open = computed({
  get: () => ui.paletteOpen,
  set: (value) => (ui.paletteOpen = value),
});
const query = ref("");

// Admin-only lists; non-admins get the actions group alone. Fetched on open so
// the palette reflects fresh data; query cleared each time it closes.
const peers = createResource({ url: "vpn_management.api.list_peers", method: "GET" });
const servers = createResource({ url: "vpn_management.api.list_servers", method: "GET" });

watch(open, (isOpen) => {
  if (!isOpen) {
    query.value = "";
    return;
  }
  if (!isAdmin.value) return;
  peers.fetch({ limit: 100 });
  servers.fetch();
});

const actionItems = computed(() => {
  const items = [];
  if (isAdmin.value) {
    items.push(action("create-peer", "Create peer", "lucide-plus", () => goPeers({ new: 1 })));
    items.push(action("settings", "Open settings", "lucide-settings", openSettings));
  } else {
    items.push(action("my-peers", "My peers", "lucide-user", () => router.push("/my-peers")));
  }
  const themeLabel = theme.dark ? "Switch to light mode" : "Switch to dark mode";
  items.push(action("theme", themeLabel, theme.dark ? "lucide-sun" : "lucide-moon", toggleTheme));
  items.push(action("shortcuts", "Keyboard shortcuts", "lucide-keyboard", openShortcuts));
  return items;
});

const peerItems = computed(() =>
  (peers.data || []).map((peer) => ({
    name: peer.name,
    title: peer.peer_name || peer.name,
    description: peer.assigned_ip || "",
    icon: "lucide-user",
    handler: () => goPeers({ focus: peer.name }),
  }))
);

const serverItems = computed(() =>
  (servers.data || []).map((server) => ({
    name: `server-${server.name}`,
    title: server.interface_name,
    description: server.address_cidr || "",
    icon: "lucide-server",
    handler: () => router.push(`/admin/servers/${server.name}/ip-map`),
  }))
);

const groups = computed(() => {
  const out = [group("Actions", actionItems.value)];
  if (isAdmin.value) {
    out.push(group("Peers", peerItems.value), group("Servers", serverItems.value));
  }
  return out.filter((entry) => entry.items.length);
});

function onSelect(item) {
  if (!item) return;
  open.value = false;
  item.handler?.();
}

// Cmd+K / Ctrl+K toggles the palette (ignored while typing in a real field).
function onKeydown(event) {
  if (event.key !== "k" || !(event.metaKey || event.ctrlKey)) return;
  event.preventDefault();
  open.value = !open.value;
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

// --- builders --------------------------------------------------------------

function action(id, title, icon, handler) {
  return { name: `action-${id}`, title, icon, handler };
}

function group(title, items) {
  return { title, items: filter(items) };
}

function filter(items) {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return items;
  return items.filter((item) => item.title.toLowerCase().includes(needle));
}

function goPeers(extraQuery) {
  router.push({ path: "/admin/peers", query: extraQuery });
}
</script>
