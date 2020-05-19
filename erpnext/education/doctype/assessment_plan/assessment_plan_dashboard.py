# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'assessment_plan',
		'non_standard_fieldnames': {
		},
		'transactions': [
			{
				'label': _('Course'),
				'items': ['Course', 'Student Group', 'Assessment Group', 'Grading Scale']
			}
		]
	}