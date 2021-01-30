from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Vehicle Masters"),
			"items": [
				{
					"type": "doctype",
					"name": "Item",
					"label": _("Vehicle Item (Variant)"),
					"description": _("Vehicle Item/Variant List"),
					"onboard": 1,
					"route_options": {
						"is_vehicle": 1
					}
				},
				{
					"type": "doctype",
					"name": "Vehicle",
					"description": _("Vehicle List."),
					"onboard": 1,
				},
			]
		},
		{
			"label": _("Transactions"),
			"items": [
				{
					"type": "doctype",
					"name": "Vehicle Booking Order",
					"onboard": 1
				},
			]
		},
		{
			"label": _("Allocation"),
			"items": [
				{
					"type": "doctype",
					"name": "Vehicle Allocation",
					"onboard": 1
				},
				{
					"type": "doctype",
					"name": "Vehicle Allocation Creation Tool",
				},
				{
					"type": "doctype",
					"name": "Vehicle Allocation Period",
				},
			]
		},
		{
			"label": _("Reports"),
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Vehicle Allocation Register",
					"doctype": "Vehicle Allocation",
					"dependencies": ["Vehicle Allocation"],
				},
			]
		},
		{
			"label": _("Settings"),
			"icon": "fa fa-cog",
			"items": [
				{
					"type": "doctype",
					"name": "Vehicles Settings",
				},
				{
					"type": "doctype",
					"name": "Vehicle Withholding Tax Rule",
				},
			]
		}
	]