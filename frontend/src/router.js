import { createRouter, createWebHistory } from "vue-router";
import { isAdmin, isGuest, loadSession } from "@/data/session";

const routes = [
	{
		path: "/my-peers",
		name: "My Peers",
		component: () => import("@/pages/MyPeers.vue"),
	},
	{
		path: "/admin",
		name: "Admin Console",
		component: () => import("@/pages/AdminPeers.vue"),
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

	const home = isAdmin.value ? "/admin" : "/my-peers";

	// Keep non-admins out of the admin console (its API calls would 403 anyway),
	// and land "/" / unknown paths on the role's home.
	if (to.path === "/admin" && !isAdmin.value) return "/my-peers";
	if (to.path !== "/my-peers" && to.path !== "/admin") return home;

	return true;
});
