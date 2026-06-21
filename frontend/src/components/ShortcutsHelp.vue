<template>
  <Dialog v-model="open" :options="{ title: 'Keyboard shortcuts', size: 'sm' }">
    <template #body-content>
      <ul class="divide-y divide-outline-gray-1">
        <li
          v-for="shortcut in shortcuts"
          :key="shortcut.label"
          class="flex items-center justify-between gap-4 py-2.5"
        >
          <span class="text-base text-ink-gray-7">{{ shortcut.label }}</span>
          <span class="flex shrink-0 items-center gap-1">
            <kbd
              v-for="key in shortcut.keys"
              :key="key"
              class="rounded border border-outline-gray-2 bg-surface-gray-2 px-1.5 py-0.5 text-xs font-medium text-ink-gray-7"
            >
              {{ key }}
            </kbd>
          </span>
        </li>
      </ul>
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted } from "vue";
import { openShortcuts, ui } from "@/data/ui";

const open = computed({
  get: () => ui.shortcutsOpen,
  set: (value) => (ui.shortcutsOpen = value),
});

const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const mod = isMac ? "⌘" : "Ctrl";

const shortcuts = [
  { label: "Open command palette", keys: [mod, "K"] },
  { label: "Show this help", keys: ["?"] },
  { label: "Dismiss dialog / palette", keys: ["Esc"] },
];

// Global "?" opens this help, except while typing in a field.
function onKeydown(event) {
  if (event.key !== "?" || event.metaKey || event.ctrlKey || event.altKey) return;
  const target = event.target;
  const typing =
    target?.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName);
  if (typing) return;
  event.preventDefault();
  openShortcuts();
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
