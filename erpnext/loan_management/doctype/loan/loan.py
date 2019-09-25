# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, math, json
import erpnext
from frappe import _
from frappe.utils import flt, rounded, add_months, nowdate, getdate, now_datetime
from erpnext.controllers.accounts_controller import AccountsController

class Loan(AccountsController):
	def validate(self):
		self.set_loan_amount()

		self.set_missing_fields()

		self.validate_loan_amount()

		self.validate_loan_security_pledge()

		if self.is_term_loan:
			validate_repayment_method(self.repayment_method, self.loan_amount, self.monthly_repayment_amount,
				self.repayment_periods, self.is_term_loan)
			self.make_repayment_schedule()
			self.set_repayment_period()

		self.calculate_totals()

	def on_submit(self):
		self.link_loan_security_pledge()

	def on_cancel(self):
		self.unlink_loan_security_pledge()

	def set_missing_fields(self):
		if not self.company:
			self.company = erpnext.get_default_company()

		if not self.posting_date:
			self.posting_date = nowdate()

		if self.loan_type and not self.rate_of_interest:
			self.rate_of_interest = frappe.db.get_value("Loan Type", self.loan_type, "rate_of_interest")

		if self.repayment_method == "Repay Over Number of Periods":
			self.monthly_repayment_amount = get_monthly_repayment_amount(self.repayment_method, self.loan_amount, self.rate_of_interest, self.repayment_periods)

	def validate_loan_security_pledge(self):

		if self.is_secured_loan and not self.loan_security_pledge:
			frappe.throw("Loan Security Pledge is mandatory for secured loan")

		if self.loan_security_pledge:
			loan = frappe.db.get_value("Loan Security Pledge", self.loan_security_pledge, 'loan')
			if loan:
				frappe.throw(_("Loan Security Pledge already pledged against loan {0}").format(loan))

	def make_repayment_schedule(self):

		if not self.repayment_start_date:
			frappe.throw("Repayment Start Date is mandatory for term loans")

		self.repayment_schedule = []
		payment_date = self.repayment_start_date
		balance_amount = self.loan_amount
		while(balance_amount > 0):
			interest_amount = rounded(balance_amount * flt(self.rate_of_interest) / (12*100))
			principal_amount = self.monthly_repayment_amount - interest_amount
			balance_amount = rounded(balance_amount + interest_amount - self.monthly_repayment_amount)

			if balance_amount < 0:
				principal_amount += balance_amount
				balance_amount = 0.0

			total_payment = principal_amount + interest_amount
			self.append("repayment_schedule", {
				"payment_date": payment_date,
				"principal_amount": principal_amount,
				"interest_amount": interest_amount,
				"total_payment": total_payment,
				"balance_loan_amount": balance_amount
			})
			next_payment_date = add_months(payment_date, 1)
			payment_date = next_payment_date

	def set_repayment_period(self):
		if self.repayment_method == "Repay Fixed Amount per Period":
			repayment_periods = len(self.repayment_schedule)

			self.repayment_periods = repayment_periods

	def calculate_totals(self):
		self.total_payment = 0
		self.total_interest_payable = 0
		self.total_amount_paid = 0

		if self.is_term_loan:
			for data in self.repayment_schedule:
				self.total_payment += data.total_payment
				self.total_interest_payable +=data.interest_amount
		else:
			self.total_payment = self.loan_amount

	def set_loan_amount(self):

		if not self.loan_amount and self.is_secured_loan and self.loan_security_pledge:
			self.loan_amount = self.maximum_loan_value

	def validate_loan_amount(self):
		if self.is_secured_loan and self.loan_amount > self.maximum_loan_value:
			msg = _("Loan amount cannot be greater than {0}".format(self.maximum_loan_value))
			frappe.throw(msg)

		if not self.loan_amount:
			frappe.throw("Loan amount is mandatory")

	def link_loan_security_pledge(self):
		frappe.db.sql("""UPDATE `tabLoan Security Pledge` SET
			loan = %s, status = 'Pledged', pledge_time = %s
			where name = %s """, (self.name, now_datetime(), self.loan_security_pledge))

	def unlink_loan_security_pledge(self):
		frappe.db.sql("""UPDATE `tabLoan Security Pledge` SET
			loan = '', status = 'Unpledged'
			where name = %s """, (self.loan_security_pledge))

def update_total_amount_paid(doc):
	total_amount_paid = 0
	for data in doc.repayment_schedule:
		if data.paid:
			total_amount_paid += data.total_payment
	frappe.db.set_value("Loan", doc.name, "total_amount_paid", total_amount_paid)

def validate_repayment_method(repayment_method, loan_amount, monthly_repayment_amount, repayment_periods, is_term_loan):

	if is_term_loan and not repayment_method:
		frappe.throw("Repayment Method is mandatory for term loans")

	if repayment_method == "Repay Over Number of Periods" and not repayment_periods:
		frappe.throw(_("Please enter Repayment Periods"))

	if repayment_method == "Repay Fixed Amount per Period":
		if not monthly_repayment_amount:
			frappe.throw(_("Please enter repayment Amount"))
		if monthly_repayment_amount > loan_amount:
			frappe.throw(_("Monthly Repayment Amount cannot be greater than Loan Amount"))

def get_monthly_repayment_amount(repayment_method, loan_amount, rate_of_interest, repayment_periods):
	if rate_of_interest:
		monthly_interest_rate = flt(rate_of_interest) / (12 *100)
		monthly_repayment_amount = math.ceil((loan_amount * monthly_interest_rate *
			(1 + monthly_interest_rate)**repayment_periods) \
			/ ((1 + monthly_interest_rate)**repayment_periods - 1))
	else:
		monthly_repayment_amount = math.ceil(flt(loan_amount) / repayment_periods)
	return monthly_repayment_amount

@frappe.whitelist()
def get_loan_application(loan_application):
	loan = frappe.get_doc("Loan Application", loan_application)
	if loan:
		return loan.as_dict()

def close_loan(loan, total_amount_paid):
	frappe.db.set_value("Loan", loan, "total_amount_paid", total_amount_paid)
	frappe.db.set_value("Loan", loan, "status", "Closed")

@frappe.whitelist()
def make_loan_disbursement(loan, loan_amount, disbursed_amount, company, applicant):
	disbursement_entry = frappe.new_doc("Loan Disbursement")
	disbursement_entry.against_loan = loan
	disbursement_entry.applicant = applicant
	disbursement_entry.company = company
	disbursement_entry.disbursement_date = nowdate()
	disbursement_entry.pending_amount_for_disbursal = flt(loan_amount) - flt(disbursed_amount)

	return disbursement_entry.as_dict()

@frappe.whitelist()
def make_repayment_entry(loan, applicant, loan_type,company):
	repayment_entry = frappe.new_doc("Loan Repayment")
	repayment_entry.against_loan = loan
	repayment_entry.applicant = applicant
	repayment_entry.company = company
	repayment_entry.loan_type = loan_type
	repayment_entry.posting_date = nowdate()

	return repayment_entry.as_dict()

@frappe.whitelist()
def create_loan_security_unpledge(loan, applicant):
	loan_security_pledge_details = frappe.db.sql("""
		SELECT p.parent, p.loan_security, p.qty as qty FROM `tabLoan Security Pledge` lsp , `tabPledge` p
		WHERE p.parent = lsp.name AND lsp.loan = %s AND lsp.docstatus = 1
	""",(loan), as_dict=1)

	unpledge_request = frappe.new_doc("Loan Security Unpledge")
	unpledge_request.applicant = applicant
	unpledge_request.loan = loan

	for loan_security in loan_security_pledge_details:
		unpledge_request.append('securities', {
			"loan_security": loan_security.loan_security,
			"qty": loan_security.qty,
			"against_pledge": loan_security.parent
		})

	return unpledge_request.as_dict()



