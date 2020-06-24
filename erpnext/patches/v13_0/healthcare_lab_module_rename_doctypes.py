from __future__ import unicode_literals
import frappe
from frappe.model.utils.rename_field import rename_field

def execute():
	# Rename fields
	frappe.reload_doc('healthcare', 'doctype', frappe.scrub('Lab Test Template'))
	if frappe.db.has_column('Lab Test Template', 'special_test_template'):
		rename_field('Lab Test Template', 'special_test_template', 'descriptive_test_templates')

	frappe.reload_doc('healthcare', 'doctype', frappe.scrub('Lab Test'))
	if frappe.db.has_column('Lab Test', 'special_test_items'):
		rename_field('Lab Test', 'special_test_items', 'descriptive_test_items')

	if frappe.db.has_column('Lab Test', 'special_toggle'):
		rename_field('Lab Test', 'special_toggle', 'descriptive_toggle')

	# Rename Options
	frappe.reload_doc('healthcare', 'doctype', frappe.scrub('Lab Test Groups'))
	frappe.db.sql("""update `tabLab Test Groups` set template_or_new_line = 'Add New Line'
			where template_or_new_line = 'Add new line'""")

	# Rename doctypes
	doctypes = {
		'Lab Test Groups': 'Lab Test Group Template',
		'Special Test Template': 'Descriptive Test Template',
		'Normal Test Items': 'Normal Test Result',
		'Special Test Items': 'Descriptive Test Result',
		'Organism Test Item': 'Organism Test Result',
		'Sensitivity Test Items': 'Sensitivity Test Result'
	}

	for old_dt, new_dt in doctypes.items():
		if not frappe.db.table_exists(new_dt) and frappe.db.table_exists(old_dt):
			frappe.reload_doc("healthcare", "doctype", frappe.scrub(old_dt))
			frappe.rename_doc('DocType', old_dt, new_dt)
			frappe.reload_doc("healthcare", "doctype", frappe.scrub(new_dt))
			frappe.delete_doc("DocType", old_dt)
