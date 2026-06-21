import { createResource } from "frappe-ui";
import { computed, reactive } from "vue";

// VPN Admins (and System Managers) get the management console; everyone else gets
// self-service. Mirrors vpn_management.permissions.is_admin on the backend.
const ADMIN_ROLES = ["VPN Admin", "System Manager"];

export const session = reactive({
	user: window.session_user || "Guest",
	roles: [],
	endpointReady: Boolean(window.endpoint_ready),
	loaded: false,
});

const userResource = createResource({
	url: "frappe.auth.get_logged_user",
	onSuccess: (user) => {
		session.user = user;
	},
});

const rolesResource = createResource({
	url: "frappe.core.doctype.user.user.get_roles",
	onSuccess: (roles) => {
		session.roles = roles || [];
	},
});

// Resolve the live session once (roles aren't on the portal boot like they are in
// Desk), then cache it so the router guard stays synchronous on later navigations.
export async function loadSession() {
	if (session.loaded) return session;
	await Promise.all([userResource.fetch(), rolesResource.fetch()]);
	session.loaded = true;
	return session;
}

export const isAdmin = computed(() => session.roles.some((role) => ADMIN_ROLES.includes(role)));

export const isGuest = computed(() => !session.user || session.user === "Guest");

// Frappe's whitelisted `logout` (POST) clears the session cookie; a full reload to
// /login then re-runs the portal boot as Guest. createResource defaults to POST.
const logoutResource = createResource({
	url: "logout",
	onSuccess: () => {
		window.location.href = "/login";
	},
});

export function logout() {
	logoutResource.submit();
}
