from __future__ import unicode_literals
import frappe

def get_data():
	vehicle_domain_sections = []
	vehicle_domain_active = 'Vehicles' in frappe.get_active_domains()
	if vehicle_domain_active:
		vehicle_domain_sections = [
			{
				'label': ['Reference'],
				'items': ['Vehicle Booking Order', 'Project']
			},
			{
				'label': ['Stock'],
				'items': ['Vehicle Receipt', 'Vehicle Delivery']
			},
			{
				'label': ['Invoice'],
				'items': ['Vehicle Invoice', 'Vehicle Invoice Delivery', 'Vehicle Invoice Movement']
			},
			{
				'label': ['Registration'],
				'items': ['Vehicle Registration Order', 'Vehicle Transfer Letter']
			},
			{
				'label': ['Sales'],
				'items': ['Quotation', 'Sales Order', 'Delivery Note', 'Sales Invoice']
			},
			{
				'label': ['Purchase'],
				'items': ['Supplier Quotation', 'Purchase Order', 'Purchase Receipt', 'Purchase Invoice']
			},
			{
				'label': ['Accounting Entries'],
				'items': ['Journal Entry', 'Payment Entry']
			},
		]

	return {
		'fieldname': 'vehicle',
		'non_standard_fieldnames': {
			'Project': 'applies_to_vehicle',
			'Journal Entry': 'applies_to_vehicle',
			'Payment Entry': 'applies_to_vehicle',
			'Quotation': 'applies_to_vehicle',
			'Sales Order': 'applies_to_vehicle',
			'Delivery Note': 'applies_to_vehicle',
			'Sales Invoice': 'applies_to_vehicle',
			'Supplier Quotation': 'applies_to_vehicle',
			'Purchase Order': 'applies_to_vehicle',
			'Purchase Receipt': 'applies_to_vehicle',
			'Purchase Invoice': 'applies_to_vehicle',
		},
		'transactions': vehicle_domain_sections + [
			{
				'label': ['Movement'],
				'items': ['Stock Entry', 'Vehicle Log']
			},
		]
	}
