import { createRouter, createWebHistory } from "vue-router";
import { isAdmin, isGuest, loadSession } from "@/data/session";

const routes = [
  {
    path: "/admin",
    name: "Dashboard",
    component: () => import("@/pages/AdminDashboard.vue"),
  },
  {
    path: "/admin/peers",
    name: "Servers & Peers",
    component: () => import("@/pages/AdminPeers.vue"),
  },
  {
    path: "/my-peers",
    name: "My Peers",
    component: () => import("@/pages/MyPeers.vue"),
  },
  // "/" and anything unrecognised fall through to the guard, which — once the
  // session has loaded — sends each role to its own home. A static redirect here
  // would resolve *before* the guard and defeat the role-based landing.
  {
    path: "/:pathMatch(.*)*",
    name: "Landing",
    component: () => import("@/pages/MyPeers.vue"),
  },
];

const ADMIN_HOME = "/admin";
const USER_HOME = "/my-peers";
const KNOWN_PATHS = new Set([ADMIN_HOME, "/admin/peers", USER_HOME]);

export const router = createRouter({
  history: createWebHistory("/vpn/"),
  routes,
});

router.beforeEach(async (to) => {
  await loadSession();

  if (isGuest.value) {
    const target = encodeURIComponent("/vpn" + to.fullPath);
    window.location.href = `/login?redirect-to=${target}`;
    return false;
  }

  // Keep non-admins out of the admin console (its API calls would 403 anyway),
  if (to.path.startsWith("/admin") && !isAdmin.value) return USER_HOME;

  // and land "/" / unknown paths on the role's home.
  if (!KNOWN_PATHS.has(to.path)) return isAdmin.value ? ADMIN_HOME : USER_HOME;

  return true;
});
