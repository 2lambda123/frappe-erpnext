# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.accounts.deferred_revenue import convert_deferred_expense_to_expense, \
	convert_deferred_revenue_to_income

class ProcessDeferredAccounting(Document):
	def validate(self):
		if self.end_date < self.start_date:
			frappe.throw(_("End date cannot be before start date"))

	def autoname(self):
		naming_series = [self.type, self.company, self.account, self.posting_date]
		self.name = '-'.join(filter(None, naming_series))

	def on_submit(self):
		conditions = self.build_conditions()

	def build_conditions(self):
		conditions=''
		deferred_account = "item.deferred_revenue_account" if self.type=="Income" else "item.deferred_expense_account"

		if self.account:
			conditions += "AND %s='%s'"%(deferred_account, self.account)
		elif self.company:
			conditions += "AND p.company='%s'"%(self.company)

		return conditions