import frappe
from erpnext.regional.india.setup import make_custom_fields

def execute():

	company = frappe.get_all('Company', filters = {'country': 'India'})
	if not company:
		return

	make_custom_fields()

	for doctype in ['Sales Invoice', 'Purchase Invoice']:
		has_column = frappe.db.has_column(doctype,'invoice_type')

		if has_column:
			update_map = {
				'Regular': 'Registered Regular',
				'Export': 'Overseas',
				'SEZ': 'SEZ',
				'Deemed Export': 'Deemed Export',
			}

			for old, new in update_map.items():
				frappe.db.sql("UPDATE `tab{doctype}` SET gst_category = %s where invoice_type = %s".format(doctype=doctype), (old, new))

	frappe.delete_doc('Custom Field', 'Sales Invoice-invoice_type')
	frappe.delete_doc('Custom Field', 'Purchase Invoice-invoice_type')

	itc_update_map = {
		"ineligible": "Ineligible",
		"input service": "Import Of Service",
		"capital goods": "Import Of Capital Goods",
		"input": "Input Service Distributor"
	}

	has_gst_fields = frappe.db.has_column('Purchase Invoice','eligibility_for_itc')

	if has_gst_fields:
		for old, new in itc_update_map.items():
			frappe.db.sql("UPDATE `tabPurchase Invoice` SET eligibility_for_itc = replace(eligibility_for_itc, %s, %s)", (old, new))



