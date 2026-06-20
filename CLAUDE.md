# SYSTEM INSTRUCTION
At the start of every session, read .claude/memory/memory.md to load project context.

After completing significant work (new patterns, architectural decisions, solved problems),

update .claude/memory/memory.md. Keep it under 300 lines — summarize when it grows.

This app runs inside a docker and this app is bind mounted to host so what ever code change is made it effect in the container directly .

The site name is `frontend`. Login is `administrator` / `W8qKn9m33Zix9r5O`.

This app runs inside Docker containers. If you want to test something, run bench commands for the site using Docker commands. 

Backend Container name : vpn_management_backend


```bash
# Tests
docker compose exec backend bench --site frontend run-tests --app vpn_management

# After ANY DocType JSON change: migrate + clear cache (schema won't apply otherwise)
docker compose exec backend bench --site frontend migrate
docker compose exec backend bench --site frontend clear-cache

# Build assets / console
docker compose exec backend bench build --app vpn_management
docker compose exec backend bench --site frontend console
```

## Guidelines for writing good code for a developer

1. Choose clean code over clever code.
2. Write object oriented code as much as possible.
3. Keep function sizes small, ideally 10 lines.
4. Try and keep files between 100 and 300 lines.
5. Don't keep too many files in a folder or module. Try and keep it under 15.
6. Avoid abbreviations.
7. Use standard API as much as possible.
8. Reuse. Write as little code as possible.
9. Use Frappe UI, espresso design system for UI styling.
10. Always write tests, and make sure they work.
11. Build the minimum working app, then iterate towards your goals.


## Skills Usage

- **agent-browser** — Use for testing any implemented feature in the browser.
- **code-style** — Use when writing or refactoring code to keep it clean and maintainable.
- **frappe-app-dev** — Use when working with Frappe-related APIs and backend logic.
- **frappe-ui** — Use when building or styling the frontend with Frappe UI.
- **ui-design** — Use when working in the Desk interface or creating DocTypes.
