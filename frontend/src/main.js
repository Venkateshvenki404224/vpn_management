import { createApp } from "vue";
import { FrappeUI, frappeRequest, setConfig } from "frappe-ui";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import "./index.css";

// Route every createResource through frappeRequest: it attaches the session
// cookie and the CSRF token (read from window.csrf_token, injected by boot).
setConfig("resourceFetcher", frappeRequest);

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(FrappeUI);
app.mount("#app");
