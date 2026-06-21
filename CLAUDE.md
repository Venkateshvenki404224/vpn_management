# SYSTEM INSTRUCTION
At the start of every session, read .claude/memory/memory.md to load project context.

After completing significant work (new patterns, architectural decisions, solved problems),

update .claude/memory/memory.md. Keep it under 300 lines — summarize when it grows.

This app runs inside a docker and this app is bind mounted to host so what ever code change is made it effect in the container directly .

The site name is `frontend`. Login is `administrator` / `W8qKn9m33Zix9r5O`.

This app runs inside Docker containers. If you want to test something, run bench commands for the site using Docker commands. 

Backend Container name : strapay_helpdesk_backend


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

## This defines the best practices to write backend code in the Frappe Framework
* Frappe Framework is a full-stack web application framework that contains all the necessary components for building modern web applications.

* It provides background workers using Redis, real-time updates using sockets, and a database layer using MariaDB.

* Bench is the official command-line tool for managing Frappe applications.

## Backend Development

### JSON & Request Handling

* Always use built-in functions for parsing JSON:

* `frappe.parse_json` (handles dicts, lists, and JSON strings safely)

* Never use `json.loads` directly on request data.

* For outbound HTTP requests (calling external APIs), use:

* `frappe.integration.utils.make_get_request`
* `frappe.integration.utils.make_post_request`
* `frappe.integration.utils.make_put_request`
* `frappe.integration.utils.make_patch_request`

### Datatype Conversion & Utilities

* For converting datatypes (e.g. str → int, str → float, etc.) use built-in helpers:

* `frappe.utils.data.cint`
* `frappe.utils.data.cstr`
* `frappe.utils.data.flt`
* `frappe.utils.data.getdate`
* `frappe.utils.data.get_datetime`

* `frappe.utils.data` contains most conversion and formatting helpers you will ever need:

* date / datetime parsing
* currency formatting
* number formatting

* Do NOT create custom utility functions for these conversions.

* If unsure, ask before implementing.

### DocType Access Patterns

* When fetching an existing DocType, prefer:

* `frappe.get_cached_doc`

* Use `frappe.get_doc` when:

* creating a new document

* To create a new doc go to bench console via bench --site sitename console and use frappe.new_doc("DocType") and then create the doc, don't create the doc via json as the validations doesn't run

### Optimization

* Don't use get_doc or get_cached_doc inside for loop it creates n+1 db problem use frappe.get_all with all the params required and then loop over that list

### Database Access

* Prefer ORM methods:

* `frappe.get_all`
* `frappe.get_list`
* `frappe.db.get_value`

* Avoid raw SQL absolutely.

### Permissions & Security

* Always respect user permissions.
* Use `ignore_permissions=True` only when absolutely required and justified.

### Background Jobs & Performance

* For long-running or heavy operations, always use:

* `frappe.enqueue`

* Never block request-response cycles with heavy business logic.

### Error Handling & Logging

* Use `frappe.throw` or specific exceptions like `frappe.ValidationError` for user-facing errors.
* Use `frappe.log_error` for unexpected or system-level exceptions.
* Avoid bare `except:` blocks.

### General Guidelines

* Prefer framework conventions over custom implementations.
* Keep business logic out of controllers where possible.
* Write readable, predictable, and maintainable code.

  
  

## Frontend Development

  
  

1. Always use async/await; avoid callback-based patterns and nested promises.

  

Use Frappe-provided APIs for server calls:

  

frappe.call with async: true

  

Prefer Promise-based usage over callbacks.

  
  

## Crawling

  
  

For checking if the site works you can use the agent-browser use agent-browser --help to get the context for it

  
  
  
  

## Joining or creating report

“Never write `frappe.db.sql` again”

===========================================================

  

1. **Ban `frappe.db.sql` in new code**

* Add a pre-commit rule or CI step that greps for `\.db\.sql` and fails the build.

* Legacy code ⇒ wrap in `frappe.db.sql("…", as_dict=1)` and add a `# TODO-QB` comment so the next refactor is trackable.

  

2. **Use the typed entry point**

```python

from frappe.query_builder import DocType, Field

from frappe.query_builder.functions import Count, Sum, Coalesce, Date

```

Never `import pypika` directly; the `frappe.qb` namespace already returns the correct `MariaDB/PostgreSQL` dialect.

  

3. **Parameterise, never interpolate**

❌ `frappe.db.sql(f"… {user_input}")` # injection bomb

✅ `frappe.qb.from_(…).where(table.field == user_input)` # auto-escaped

  

4. **Prefer joins over N+1**

```python

so = DocType("Sales Order")

si = DocType("Sales Invoice")

query = (

frappe.qb.from_(so)

.left_join(si)

.on(so.name == si.sales_order)

.select(so.name, si.name)

.where(so.customer == customer)

)

```

One round-trip, no loops.

  

5. **Sub-queries > raw SQL strings**

Need *“latest row per group”*?

```python

latest = (

frappe.qb.from_(si)

.select(si.name)

.where(si.sales_order == so.name)

.orderby(si.creation, order=Order.desc)

.limit(1)

)

query = frappe.qb.from_(so).where(so.name == latest)

```

Keeps everything composable and dialect-agnostic.

  

6. **Use `case` for conditional aggregates**

```python

from frappe.query_builder.functions import Case

paid_amt = Sum(

Case()

.when(si.status == "Paid", si.grand_total)

.else_(0)

)

```

  

7. **Respect Frappe field casing**

* SQL column: `grand_total`

* Frappe field: `grand_total`

* No back-ticks needed; QB adds the correct quotes per DB.

  

8. **Use `as_dict=True` or ORM objects**

```python

rows = query.run(as_dict=True) # list[dict]

# or

docs = query.run(as_dict=False) # list[tuple]

# or

obj = frappe.get_doc("Doctype", pk) # when you need the full DocType hooks

```

  

9. **Pagination with `limit_page_length` and `limit_start`**

```python

query = query.limit(limit_page_length).offset(limit_start)

```

Same pattern the REST API uses.

  

10. **Index-friendly WHERE order**

Put indexed columns first (`company`, `customer`, `status`) so MariaDB/PostgreSQL can use composite indexes.

  

11. **Avoid `SELECT *` in reports**

Explicit list of fields keeps wire-size small and prevents breaking changes when new fields are added.

  
  
  

13. **Cache heavy aggregations**

```python

@frappe.whitelist()

@redis_cache(ttl=300)

def get_dashboard_stats(company):

inv = DocType("Sales Invoice")

total = frappe.qb.from_(inv).select(Sum(inv.grand_total)).where(inv.company == company).run()

return total[0][0] or 0

```

Quick migration template

----------------------


Legacy:

```python

rows = frappe.db.sql("""

select name, grand_total

from `tabSales Invoice`

where customer = %s

and docstatus = 1

""", customer, as_dict=1)

```


QB equivalent:

```python

si = DocType("Sales Invoice")

rows = (

frappe.qb.from_(si)

.select(si.name, si.grand_total)

.where((si.customer == customer) & (si.docstatus == 1))

.run(as_dict=True)

)

```