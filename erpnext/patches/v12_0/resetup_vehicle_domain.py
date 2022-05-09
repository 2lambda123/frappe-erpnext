# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	frappe.reload_doc("projects", "doctype", "project")
	frappe.reload_doc("projects", "doctype", "project_type")
	frappe.reload_doc("projects", "doctype", "project_template")
	frappe.reload_doc("projects", "doctype", "project_template_category")

	domain = 'Vehicles'
	if domain in frappe.get_active_domains():
		doc = frappe.get_doc("Domain", "Vehicles")
		doc.setup_domain()
