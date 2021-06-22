from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'work_order',
		'transactions': [
			{
				'label': _('Transactions'),
				'items': ['Stock Entry', 'Job Card', 'Pick List', 'Additional Item']
			},
			{
				'label': _('Material'),
				'items': ['Material Request', 'Material Consumption', 'Material Produce']
			},
		]
	}