app_name = "vpn_management"
app_title = "Vpn Management"
app_publisher = "Venkatesh"
app_description = "The VPN Management App"
app_email = "venkateshvenki404224@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "vpn_management",
# 		"logo": "/assets/vpn_management/logo.png",
# 		"title": "Vpn Management",
# 		"route": "/vpn_management",
# 		"has_permission": "vpn_management.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vpn_management/css/vpn_management.css"
# app_include_js = "/assets/vpn_management/js/vpn_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/vpn_management/css/vpn_management.css"
# web_include_js = "/assets/vpn_management/js/vpn_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "vpn_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vpn_management/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "vpn_management.utils.jinja_methods",
# 	"filters": "vpn_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "vpn_management.install.before_install"
after_install = "vpn_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "vpn_management.uninstall.before_uninstall"
# after_uninstall = "vpn_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vpn_management.utils.before_app_install"
# after_app_install = "vpn_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vpn_management.utils.before_app_uninstall"
# after_app_uninstall = "vpn_management.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "vpn_management.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vpn_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		# Read live handshake/rx/tx back onto peers every 5 minutes.
		"*/5 * * * *": ["vpn_management.tasks.poll_status"],
		# Drift-correct the fleet and re-converge from the DB every 10 minutes.
		"*/10 * * * *": ["vpn_management.tasks.reconcile_all"],
	},
}

# Testing
# -------

# before_tests = "vpn_management.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "vpn_management.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vpn_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vpn_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vpn_management.utils.before_request"]
# after_request = ["vpn_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["vpn_management.utils.before_job"]
# after_job = ["vpn_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"vpn_management.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# The poll/reconcile crons append to VPN Audit Log continuously; retain 90 days.
# Frappe's daily log clean-up prunes rows past this via the controller's
# clear_old_logs LogType hook (VPNAuditLog.clear_old_logs).
default_log_clearing_doctypes = {
	"VPN Audit Log": 90,
}

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
