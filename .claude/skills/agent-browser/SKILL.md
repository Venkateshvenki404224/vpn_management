---
name: agent-browser
description: Browser automation and testing using the agent-browser CLI tool. Use this skill whenever the user wants to interact with a web application through a browser, test UI behavior, automate form submissions, verify page content, take screenshots, debug frontend issues, or perform any browser-based task. Also trigger when the user says things like "check the site", "open the page", "click the button", "fill the form", "test the login", "take a screenshot", "see what the page looks like", or references browser testing, UI verification, or web automation. Prefer this over Playwright for quick interactive browser tasks since agent-browser is optimized for AI agents with compact token output.
---

# Agent-Browser: AI-Optimized Browser Automation

agent-browser is a Rust CLI that controls a real browser via Chrome DevTools Protocol. It produces compact, token-efficient text output (200-400 tokens vs 3000-5000 for full DOM) making it ideal for AI-driven browser interaction.

## Quick Reference

```bash
# The CLI — always use npx with pinned version (the local binary segfaults)
npx agent-browser@0.21.4 <command> [args] [options]
```

**Important**: Always use `npx agent-browser@0.21.4` (not just `npx agent-browser` or the local binary). All examples below use `npx agent-browser` for brevity — always substitute `npx agent-browser@0.21.4` when running.

**Default target site**: `http://sponge.localhost:8014` (Frappe/ERPNext)

## Core Workflow: Snapshot-Act-Verify

Every browser interaction follows this loop:

1. **Navigate** to the page
2. **Snapshot** to get the accessibility tree with element refs
3. **Act** on elements using their `@eN` refs
4. **Verify** the result with another snapshot or screenshot

This pattern matters because refs (`@e1`, `@e2`, etc.) are invalidated when the page changes. Always re-snapshot after navigation or actions that modify the DOM.

### Example: Log into Frappe

```bash
# 1. Open the login page
npx agent-browser open http://sponge.localhost:8014

# 2. Snapshot to discover elements
npx agent-browser snapshot -i
# Output:
# - heading "Login to Frappe" [level=4, ref=e1]
# - textbox "Email" [required, ref=e4]
# - textbox "Password" [required, ref=e5]
# - button "Login" [ref=e2]

# 3. Fill the form and submit
npx agent-browser fill @e4 "Administrator"
npx agent-browser fill @e5 "password"
npx agent-browser click @e2

# 4. Wait for navigation, then verify
npx agent-browser wait --load networkidle
npx agent-browser snapshot -i
```

### Example: Navigate Frappe Desk and Verify Content

```bash
# After login, go to a specific doctype list
npx agent-browser open http://sponge.localhost:8014/app/employee

# Wait for the list to render (Frappe uses client-side routing)
npx agent-browser wait --load networkidle
npx agent-browser snapshot -i -d 3

# Take a screenshot for visual verification
npx agent-browser screenshot /tmp/employee-list.png
```

## Element Selection

**Refs (preferred)**: Use `@eN` refs from snapshots for deterministic selection.
```bash
npx agent-browser click @e2
npx agent-browser fill @e3 "some text"
```

**CSS selectors**: When you know the selector.
```bash
npx agent-browser click "#submit-btn"
npx agent-browser click "[data-doctype='Employee']"
```

**Text/XPath**: For text-based or complex selection.
```bash
npx agent-browser click "text=Submit"
npx agent-browser click "xpath=//button[@type='submit']"
```

**Semantic locators**: Find by accessibility properties.
```bash
npx agent-browser find role button click --name "Save"
npx agent-browser find label "Email" fill "user@example.com"
npx agent-browser find placeholder "Search..." fill "query"
```

## Snapshot Options

Snapshots are your primary tool for understanding page state.

| Flag | Purpose | When to use |
|------|---------|-------------|
| `-i` | Interactive elements only | Most of the time — buttons, links, inputs |
| `-c` | Remove empty structural elements | Cleaner output for complex pages |
| `-d N` | Limit tree depth | Deep/nested pages like Frappe forms |
| `-s "selector"` | Scope to CSS selector | Focus on a specific section |

Combine flags: `npx agent-browser snapshot -i -c -d 5`

For visual verification: `npx agent-browser screenshot --annotate` overlays numbered labels on elements.

## Essential Commands

### Navigation
```bash
npx agent-browser open <url>          # Navigate to URL
npx agent-browser back                # Go back
npx agent-browser forward             # Go forward
npx agent-browser reload              # Reload page
```

### Form Interaction
```bash
npx agent-browser fill @eN "text"     # Clear field and type
npx agent-browser type @eN "text"     # Type into element (appends)
npx agent-browser click @eN           # Click element
npx agent-browser select @eN "value"  # Select dropdown option
npx agent-browser check @eN           # Check checkbox
npx agent-browser uncheck @eN         # Uncheck checkbox
npx agent-browser press Enter         # Press key (Enter, Tab, Escape, etc.)
```

### Information Retrieval
```bash
npx agent-browser get text @eN        # Get text content
npx agent-browser get value @eN       # Get input value
npx agent-browser get title           # Page title
npx agent-browser get url             # Current URL
```

### Waiting (Critical for Frappe's SPA)
Frappe is a single-page app — pages often load asynchronously. Always wait after navigation.

```bash
npx agent-browser wait --load networkidle    # Wait for network to settle
npx agent-browser wait --text "Welcome"      # Wait for specific text
npx agent-browser wait --url "**/app/home"   # Wait for URL pattern
npx agent-browser wait @eN                   # Wait for element to appear
npx agent-browser wait @eN --state hidden    # Wait for element to disappear
npx agent-browser wait 2000                  # Wait N milliseconds
```

### Screenshots
```bash
npx agent-browser screenshot /tmp/page.png          # Current viewport
npx agent-browser screenshot /tmp/full.png --full    # Full page
npx agent-browser screenshot --annotate              # With element labels
```

### JavaScript Execution
```bash
npx agent-browser eval "document.title"
npx agent-browser eval "cur_frm.doc.name"           # Frappe-specific: get current form doc
npx agent-browser eval "frappe.session.user"         # Get logged-in user
```

### Scrolling
```bash
npx agent-browser scroll down 500
npx agent-browser scroll up 300
npx agent-browser scrollintoview @eN
```

### Tabs
```bash
npx agent-browser tab                  # List tabs
npx agent-browser tab new <url>        # Open new tab
npx agent-browser tab 2                # Switch to tab 2
npx agent-browser tab close            # Close current tab
```

## Frappe-Specific Patterns

Frappe's Desk UI has specific behaviors that affect browser automation:

### Awesomebar Search
```bash
npx agent-browser open http://sponge.localhost:8014
npx agent-browser wait --load networkidle
npx agent-browser snapshot -i
# Find the awesomebar input and type into it
npx agent-browser fill @eN "Employee"
npx agent-browser press Enter
npx agent-browser wait --load networkidle
```

### Form Interactions
Frappe forms use custom widgets (Link fields, Select fields, etc.) that may not behave like standard HTML inputs.

```bash
# For Link fields, type and wait for the dropdown
npx agent-browser fill @eN "HR-EMP"
npx agent-browser wait 1000
npx agent-browser snapshot -i   # Look for dropdown suggestions
npx agent-browser click @eM     # Click the suggestion

# For saving a form
npx agent-browser find role button click --name "Save"
# Or use keyboard shortcut
npx agent-browser press Control+s
```

### Sidebar Navigation
```bash
# Open sidebar module
npx agent-browser snapshot -i -s ".sidebar-menu"
npx agent-browser click @eN   # Click module link
npx agent-browser wait --load networkidle
```

### Dialog Handling
```bash
# After an action triggers a dialog
npx agent-browser wait ".modal-dialog"
npx agent-browser snapshot -i -s ".modal-dialog"
npx agent-browser fill @eN "value"
npx agent-browser find role button click --name "Submit"
```

## Sessions

Use sessions to maintain isolated browser states (e.g., different logged-in users):

```bash
# Create named sessions
npx agent-browser --session admin open http://sponge.localhost:8014
npx agent-browser --session employee open http://sponge.localhost:8014

# Each session has its own cookies, storage, and auth
npx agent-browser --session admin snapshot -i
npx agent-browser --session employee snapshot -i
```

## State Management

Save and restore browser state (cookies, localStorage) across runs:

```bash
npx agent-browser state save /tmp/logged-in.json
npx agent-browser state load /tmp/logged-in.json
```

## Network Monitoring

Useful for debugging API calls in Frappe:

```bash
npx agent-browser network requests --filter "**/api/**" --method POST
npx agent-browser network request <requestId>    # Full details
```

## Closing the Browser

```bash
npx agent-browser close
```

## Common Pitfalls

1. **Don't act on stale refs** — Always re-snapshot after page changes. Refs from a previous snapshot point to elements that may no longer exist.

2. **Wait after Frappe navigation** — Frappe's SPA routing means the URL changes but content loads asynchronously. Always `wait --load networkidle` after `open` or clicking navigation links.

3. **Frappe Link fields need special handling** — They're autocomplete widgets, not simple inputs. Type, wait for suggestions, then click one.

4. **Use `snapshot -i`** by default — The full accessibility tree is verbose. `-i` (interactive only) gives you just the actionable elements.

5. **Screenshot for visual debugging** — When snapshots don't tell the full story, take a screenshot to see what's actually rendered.

## Full Command Reference

For the complete list of 50+ commands (network interception, cookies, storage, auth profiles, HAR recording, tracing, video recording, clipboard, dialogs, mouse operations, etc.), see [references/commands.md](references/commands.md).
