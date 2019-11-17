# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime
from frappe.model.document import Document
from erpnext.loan_management.doctype.loan_security_shortfall.loan_security_shortfall import update_shortfall_status
from erpnext.loan_management.doctype.loan_security_price.loan_security_price import get_loan_security_price

class LoanSecurityPledge(Document):
	def validate(self):
		self.set_pledge_amount()

	def on_submit(self):
		if self.loan:
			self.db_set("status", "Pledged")
			self.db_set("pledge_time", now_datetime())
			update_shortfall_status(self.loan, self.total_security_value)

	def set_pledge_amount(self):
		total_security_value = 0
		maximum_loan_value = 0

		for pledge in self.securities:
			pledge.loan_security_price = get_loan_security_price(pledge.loan_security)
			pledge.amount = pledge.qty * pledge.loan_security_price

			total_security_value += pledge.amount
			maximum_loan_value += pledge.amount - (pledge.amount * pledge.haircut)/100

		self.total_security_value = total_security_value
		self.maximum_loan_value = maximum_loan_value
