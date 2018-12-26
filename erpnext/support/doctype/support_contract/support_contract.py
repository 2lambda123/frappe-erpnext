# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class SupportContract(Document):

	def before_insert(self):
		if self.default_contract:
			doc = frappe.get_list("Support Contract", filters=[{"default_contract": "1"}])
			if doc:
				frappe.throw(_("There can't be two Default Support Contracts"))

	def validate(self):
		if not self.default_contract:
			if self.start_date >= self.end_date:
				frappe.throw(_("Support Start Date of contract can't be greater than or equal to End Date"))