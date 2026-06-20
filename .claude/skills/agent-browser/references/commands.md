# Agent-Browser Full Command Reference

All commands use the prefix: `npx agent-browser`

## Table of Contents
- [Navigation](#navigation)
- [Interaction](#interaction)
- [Form Controls](#form-controls)
- [Scrolling & Movement](#scrolling--movement)
- [Information Retrieval](#information-retrieval)
- [State Checking](#state-checking)
- [Waiting](#waiting)
- [Screenshots & Capture](#screenshots--capture)
- [Semantic Locators](#semantic-locators)
- [Keyboard & Mouse](#keyboard--mouse)
- [Clipboard](#clipboard)
- [Tabs & Frames](#tabs--frames)
- [Dialogs](#dialogs)
- [Network](#network)
- [Cookies & Storage](#cookies--storage)
- [Sessions & State](#sessions--state)
- [Authentication](#authentication)
- [Settings](#settings)
- [Debugging & Profiling](#debugging--profiling)
- [Global Options](#global-options)

---

## Navigation
| Command | Description |
|---------|-------------|
| `open <url>` | Navigate to URL (aliases: goto, navigate) |
| `back` | Go back |
| `forward` | Go forward |
| `reload` | Reload page |
| `close` | Close browser (aliases: quit, exit) |

## Interaction
| Command | Description |
|---------|-------------|
| `click <sel>` | Click element (--new-tab for new tab) |
| `dblclick <sel>` | Double-click element |
| `hover <sel>` | Hover over element |
| `focus <sel>` | Focus element |
| `drag <src> <dst>` | Drag and drop |
| `upload <sel> <files>` | Upload files |
| `highlight <sel>` | Highlight element visually |

## Form Controls
| Command | Description |
|---------|-------------|
| `fill <sel> <text>` | Clear field and type text |
| `type <sel> <text>` | Type into element (appends) |
| `select <sel> <val>` | Select dropdown option |
| `check <sel>` | Check checkbox |
| `uncheck <sel>` | Uncheck checkbox |
| `press <key>` | Press key (Enter, Tab, Control+a, etc.) |

## Scrolling & Movement
| Command | Description |
|---------|-------------|
| `scroll <dir> [px]` | Scroll up/down/left/right (--selector for element) |
| `scrollintoview <sel>` | Scroll element into view |

## Information Retrieval
| Command | Description |
|---------|-------------|
| `snapshot` | Accessibility tree with refs |
| `snapshot -i` | Interactive elements only |
| `snapshot -c` | Compact (no empty structural nodes) |
| `snapshot -d N` | Limit depth to N levels |
| `snapshot -s "css"` | Scope to CSS selector |
| `get text <sel>` | Get text content |
| `get html <sel>` | Get innerHTML |
| `get value <sel>` | Get input value |
| `get attr <sel> <attr>` | Get attribute |
| `get title` | Page title |
| `get url` | Current URL |
| `get count <sel>` | Count matching elements |
| `get box <sel>` | Bounding box |
| `get styles <sel>` | Computed styles |
| `eval <js>` | Execute JavaScript |

## State Checking
| Command | Description |
|---------|-------------|
| `is visible <sel>` | Check visibility |
| `is enabled <sel>` | Check if enabled |
| `is checked <sel>` | Check if checked |

## Waiting
| Command | Description |
|---------|-------------|
| `wait <selector>` | Wait for element |
| `wait <ms>` | Wait specified milliseconds |
| `wait --text "str"` | Wait for text substring |
| `wait --url "pattern"` | Wait for URL pattern |
| `wait --load networkidle` | Wait for network to settle |
| `wait --fn "js condition"` | Wait for JS condition |
| `wait --download [path]` | Wait for download |
| `wait <sel> --state hidden` | Wait for element to disappear |

## Screenshots & Capture
| Command | Description |
|---------|-------------|
| `screenshot [path]` | Capture viewport |
| `screenshot --full` | Full page screenshot |
| `screenshot --annotate` | With numbered element labels |
| `screenshot --screenshot-format jpeg --screenshot-quality 80` | JPEG with quality |
| `pdf <path>` | Save as PDF |

## Semantic Locators
| Command | Description |
|---------|-------------|
| `find role <role> <action> [value]` | Find by ARIA role |
| `find text <text> <action>` | Find by visible text |
| `find label <label> <action> [value]` | Find by label |
| `find placeholder <ph> <action> [value]` | Find by placeholder |
| `find alt <text> <action>` | Find by alt text |
| `find title <text> <action>` | Find by title |
| `find testid <id> <action> [value]` | Find by data-testid |
| `find first <sel> <action> [value]` | First match |
| `find last <sel> <action> [value]` | Last match |
| `find nth <n> <sel> <action> [value]` | Nth match |

Options: `--name <name>`, `--exact`

## Keyboard & Mouse
| Command | Description |
|---------|-------------|
| `press <key>` | Press key (alias: key) |
| `keyboard type <text>` | Type at current focus |
| `keyboard inserttext <text>` | Insert text without key events |
| `keydown <key>` | Hold key down |
| `keyup <key>` | Release key |
| `mouse move <x> <y>` | Move mouse |
| `mouse down [button]` | Press mouse button |
| `mouse up [button]` | Release button |
| `mouse wheel <dy> [dx]` | Scroll wheel |

## Clipboard
| Command | Description |
|---------|-------------|
| `clipboard read` | Get clipboard text |
| `clipboard write "text"` | Set clipboard text |
| `clipboard copy` | Copy selection (Ctrl+C) |
| `clipboard paste` | Paste (Ctrl+V) |

## Tabs & Frames
| Command | Description |
|---------|-------------|
| `tab` | List tabs |
| `tab new [url]` | New tab |
| `tab <n>` | Switch to tab N |
| `tab close [n]` | Close tab |
| `window new` | Open new window |
| `frame <sel>` | Switch to iframe |
| `frame main` | Back to main frame |

## Dialogs
| Command | Description |
|---------|-------------|
| `dialog accept [text]` | Accept dialog |
| `dialog dismiss` | Dismiss dialog |

## Network
| Command | Description |
|---------|-------------|
| `network requests` | View tracked requests |
| `network requests --filter <pattern>` | Filter by URL pattern |
| `network requests --type xhr,fetch` | Filter by type |
| `network requests --method POST` | Filter by HTTP method |
| `network requests --status 2xx` | Filter by status |
| `network requests --clear` | Clear request log |
| `network request <requestId>` | Full request details |
| `network route <url>` | Intercept requests |
| `network route <url> --abort` | Block requests |
| `network route <url> --body <json>` | Mock response |
| `network unroute [url]` | Remove routes |
| `network har start` | Start HAR recording |
| `network har stop [output.har]` | Stop and save HAR |

## Cookies & Storage
| Command | Description |
|---------|-------------|
| `cookies` | Get all cookies |
| `cookies set <name> <val>` | Set cookie |
| `cookies clear` | Clear cookies |
| `storage local` | Get all localStorage |
| `storage local <key>` | Get specific key |
| `storage local set <k> <v>` | Set value |
| `storage local clear` | Clear localStorage |
| `storage session` | Same commands for sessionStorage |

## Sessions & State
| Command | Description |
|---------|-------------|
| `session` | Show current session |
| `session list` | List active sessions |
| `state save <path>` | Save state to file |
| `state load <path>` | Load state from file |
| `state list` | List saved states |
| `state clear [name]` | Clear session states |
| `state clear --all` | Clear all states |

Use `--session <name>` on any command for isolated sessions.

## Authentication
| Command | Description |
|---------|-------------|
| `auth save <name> --url <url> --username <u> --password <p>` | Save credentials |
| `auth login <name>` | Login with saved profile |
| `auth list` | List profiles |
| `auth show <name>` | Show profile metadata |
| `auth delete <name>` | Delete profile |

## Settings
| Command | Description |
|---------|-------------|
| `set viewport <w> <h> [scale]` | Set viewport size |
| `set device <name>` | Emulate device (e.g., "iPhone 14") |
| `set geo <lat> <lng>` | Set geolocation |
| `set offline [on\|off]` | Toggle offline mode |
| `set headers <json>` | Add HTTP headers |
| `set credentials <u> <p>` | HTTP basic auth |
| `set media [dark\|light]` | Color scheme |

## Debugging & Profiling
| Command | Description |
|---------|-------------|
| `console` | View console messages |
| `console --clear` | Clear console |
| `errors` | View page errors |
| `errors --clear` | Clear errors |
| `trace start [path]` | Start trace |
| `trace stop [path]` | Stop and save trace |
| `profiler start` | Start DevTools profiling |
| `profiler stop [path]` | Stop and save profile |
| `record start <path>` | Start video recording (WebM) |
| `record stop` | Stop video |
| `inspect` | Open Chrome DevTools |
| `connect <port\|url>` | CDP connection |

## Global Options
| Option | Description |
|--------|-------------|
| `--session <name>` | Isolated browser session |
| `--headed` | Show browser window |
| `--json` | JSON output |
| `--cdp <port\|url>` | CDP connection |
| `--auto-connect` | Auto-discover Chrome |
| `--proxy <url>` | Proxy server |
| `--ignore-https-errors` | Ignore HTTPS errors |
| `--debug` | Debug output |
| `--max-output <chars>` | Truncate output |
| `--allowed-domains <list>` | Domain whitelist |
