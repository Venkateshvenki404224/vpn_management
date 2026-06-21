<template>
  <div class="flex min-h-screen flex-col bg-surface-gray-1 text-ink-gray-9">
    <header class="sticky top-0 z-10 border-b border-outline-gray-2 bg-surface-white">
      <div
        class="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4"
      >
        <div class="flex items-center gap-6">
          <RouterLink
            to="/"
            class="flex items-center gap-2 font-semibold text-ink-gray-9"
          >
            <img :src="logoUrl" alt="VPN Management" class="size-6 rounded" />
            VPN Management
          </RouterLink>
          <nav v-if="isAdmin" class="flex items-center gap-1">
            <RouterLink
              v-for="link in links"
              :key="link.to"
              :to="link.to"
              class="rounded px-2.5 py-1 text-sm font-medium text-ink-gray-6 hover:bg-surface-gray-2"
              :class="isLinkActive(link) && 'bg-surface-gray-3 !text-ink-gray-9'"
            >
              {{ link.label }}
            </RouterLink>
          </nav>
        </div>
        <span class="hidden text-sm text-ink-gray-5 sm:inline">{{
          session.user
        }}</span>
      </div>
    </header>

    <main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from "vue-router";
import { isAdmin, session } from "@/data/session";

// Served from the app's public/ via the /assets symlink. Kept as a runtime
// string so Vite doesn't try to resolve it as a build-time asset.
const logoUrl = "/assets/vpn_management/images/logo.png";

const links = [
  { to: "/admin", label: "Dashboard", exact: true },
  { to: "/admin/peers", label: "Servers & Peers" },
  { to: "/my-peers", label: "My Peers" },
];

// Exact match for the dashboard so it doesn't stay lit on "/admin/peers";
// prefix match for the rest. RouterLink's own active-class is inclusive, which
// would highlight "/admin" on every nested admin route.
const route = useRoute();
function isLinkActive(link) {
  return link.exact ? route.path === link.to : route.path.startsWith(link.to);
}
</script>
