# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ServiceLevel(Document):
	
	def validate(self):
		for support_and_resolution in self.support_and_resolution:
			pass