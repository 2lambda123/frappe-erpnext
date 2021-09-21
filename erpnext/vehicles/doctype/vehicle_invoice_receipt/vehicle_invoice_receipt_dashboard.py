from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'vehicle_invoice_receipt',
		'transactions': [
			{
				'label': _('Reference'),
				'items': ['Vehicle Invoice Delivery']
			}
		]
	}
