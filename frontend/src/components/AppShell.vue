<template>
  <div class="flex h-screen bg-surface-gray-1 text-ink-gray-9">
    <Sidebar
      v-model:collapsed="collapsed"
      :header="header"
      :sections="sections"
    />
    <main class="flex-1 overflow-y-auto">
      <!-- Full-bleed content (helpdesk pattern): fill the rail's remaining width
           with even padding instead of a centered max-w column, so there are no
           empty gutters on the left and right. -->
      <div class="w-full px-6 py-6">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { Sidebar } from "frappe-ui";
import { isAdmin, logout, session } from "@/data/session";

// Served from the app's public/ via the /assets symlink. Kept as a runtime
// string so Vite doesn't try to resolve it as a build-time asset.
const logoUrl = "/assets/vpn_management/images/logo.png";

// Persist the collapse choice. Seed `null` (not `false`) when unset so the
// Sidebar's own mobile fallback (`collapsed ?? isMobile`) still auto-collapses
// the rail below the `sm` breakpoint. Native localStorage — no new dependency.
const STORAGE_KEY = "vpn_sidebar_collapsed";

function readCollapsed() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === null ? null : stored === "true";
}

const collapsed = ref(readCollapsed());

watch(collapsed, (value) => {
  if (value === null) localStorage.removeItem(STORAGE_KEY);
  else localStorage.setItem(STORAGE_KEY, String(value));
});

// Brand + account header. The session is resolved by the router guard before any
// page (and thus this shell) mounts, so `session.user` is the real user here.
const header = {
  title: "VPN Management",
  subtitle: session.user,
  logo: logoUrl,
  menuItems: [{ label: "Logout", icon: "lucide-log-out", onClick: logout }],
};

// SidebarItem resolves active state by route name, and SidebarSection hides any
// item whose `condition` is false — so admin links role-gate via `isAdmin`.
const sections = [
  {
    items: [
      {
        label: "Dashboard",
        icon: "lucide-layout-dashboard",
        to: "/admin",
        condition: isAdmin,
      },
      {
        label: "Servers & Peers",
        icon: "lucide-server",
        to: "/admin/peers",
        condition: isAdmin,
      },
      { label: "My Peers", icon: "lucide-user", to: "/my-peers" },
    ],
  },
];
</script>
