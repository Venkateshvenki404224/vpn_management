import vue from "@vitejs/plugin-vue";
import path from "path";
import { defineConfig } from "vite";
import frappeui from "frappe-ui/vite";

// The frappeui plugin's buildConfig rewrites the built index.html (with hashed
// asset tags + the jinja boot loop) straight into www/vpn/index.html, so no
// `bench build` asset-include hook is needed once the /assets symlink exists.
export default defineConfig({
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: true,
			jinjaBootData: true,
			buildConfig: {
				outDir: "../vpn_management/public/frontend",
				emptyOutDir: true,
				indexHtmlPath: "../vpn_management/www/vpn/index.html",
				baseUrl: "/assets/vpn_management/frontend/",
				// The built assets are committed (this app is deployed by git pull, not a
				// release build), so skip sourcemaps to keep them out of the repo.
				sourcemap: false,
			},
		}),
		vue(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			"tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
		},
	},
	optimizeDeps: {
		include: ["feather-icons", "tailwind.config.js"],
		exclude: ["frappe-ui"],
	},
});
