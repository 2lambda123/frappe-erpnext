# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, throw
from frappe.model.document import Document

class DebitNoteCXP(Document):
	def validate(self):
		self.verificate_references_and_amount()
		self.calculate_total()
		if self.docstatus == 1:
			self.verificate_amount()
			self.update_accounts_status()

	def calculate_total(self):
		if not self.get("references"):
			frappe.throw(_(" Required references"))
		total_reference = 0
		for d in self.get("references"):
			total_reference += d.total_amount
			self.total_references = total_reference
		
		if self.total_exempt > self.total_references:
			frappe.throw(_("Amount cannot be greater than the total references"))

		self.calculate_isv()
		total_base = 0
		if len(self.get("references")) > 0:
			if self.total_exempt != None:
				if not self.get("taxes"):
					self.amount_total = self.total_exempt
				else:
					for taxes_list in self.get("taxes"):
						total_base += taxes_list.base_isv
						if self.total_exempt != None:
							self.amount_total = total_base + self.total_exempt
						else:
							self.amount_total = total_base
						if self.isv_15 != None:
							self.amount_total = total_base + self.total_exempt + self.isv_15
						elif self.isv_18 != None:
							self.amount_total = total_base + self.total_exempt + self.isv_18
	
	def calculate_isv(self):
		for taxes_list in self.get("taxes"):
			item_tax_template = frappe.get_all("Item Tax Template", ["name"], filters = {"name": taxes_list.isv})
			for tax_template in item_tax_template:
				tax_details = frappe.get_all("Item Tax Template Detail", ["name", "tax_rate"], filters = {"parent": tax_template.name})
				for tax in tax_details:
					if tax.tax_rate == 15:
						tx_base = taxes_list.base_isv * (tax.tax_rate/100)
						self.isv_15 = tx_base
					elif tax.tax_rate == 18:
						tx_base = taxes_list.base_isv * (tax.tax_rate/100)
						self.isv_18 = tx_base

	def verificate_references_and_amount(self):
		if len(self.get("references")) > 1:
			order_by = sorted(self.references, key=lambda item: item.total_amount)
			remaining_amount = self.amount
			for d in order_by:
				if remaining_amount <= d.total_amount:
					result = d.total_amount - remaining_amount
					if result <= 0:
						frappe.throw(_("The amount can not be accepted to pay the bills, the amount must pay the bills or pay one and advance another."))

	def verificate_amount(self):
		remaining = 0
		amount_total = self.amount_total
		if len(self.get("references")) > 1:
			for d in sorted(self.references, key=lambda item: item.total_amount):
				purchase_invoice = frappe.get_doc("Purchase Invoice", d.reference_name)
				if amount_total > d.total_amount:
					amount_total -= d.total_amount
					purchase_invoice.outstanding_amount -= d.total_amount
				else:
					if amount_total <= d.total_amount:
						purchase_invoice.outstanding_amount -= amount_total
				purchase_invoice.save()
		else: 
			for x in self.get("references"):
				if amount_total <= x.total_amount:
					purchase_invoice = frappe.get_doc("Purchase Invoice", x.reference_name)
					purchase_invoice.outstanding_amount -= self.amount_total
				purchase_invoice.save()
	
	def update_accounts_status(self):
		supplier = frappe.get_doc("Supplier", self.supplier)
		if supplier:
			supplier.debit += self.amount_total
			supplier.save()