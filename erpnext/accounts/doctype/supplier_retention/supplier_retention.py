# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, throw
from frappe.utils import getdate, nowdate
from frappe.model.document import Document
from datetime import datetime, timedelta, date
from frappe.model.naming import parse_naming_series

class SupplierRetention(Document):
	def validate(self):
		self.calculate_percentage_and_references()
		if self.docstatus == 1:
			self.calculate_retention()

	def calculate_percentage_and_references(self):
		if self.get("reasons"):
			total_percentage = 0
			for item in self.get("reasons"):
				total_percentage += item.percentage
			self.percentage_total = total_percentage
		if self.get("references"):
			total_references = 0
			withheld = 0
			for item in self.get("references"):
				total_references += item.net_total
				withheld += item.net_total * (self.percentage_total/100)
			self.total_references = total_references
			self.total_withheld = withheld
	
	def calculate_retention(self):
		for document in self.get("references"):
			total = document.net_total * (self.percentage_total/100)
			sales_invoice = frappe.get_doc("Purchase Invoice", document.reference_name)
			sales_invoice.outstanding_amount -= total
			sales_invoice.save()

	def assign_cai(self):
		cai = frappe.get_all("CAI", ["initial_number", "final_number", "name_cai", "cai", "issue_deadline", "prefix"], filters = { "status": "Active", "prefix": self.naming_series})
		if len(cai) == 0:
			frappe.throw(_("This secuence no assing cai"))
		current_value = self.get_current(cai[0].prefix)

		now = datetime.now()

		date = now.date()

		if current_value + 1 <= int(cai[0].final_number) and str(date) <= str(cai[0].issue_deadline):
			self.assing_data(cai[0].cai, cai[0].issue_deadline, cai[0].initial_number, cai[0].final_number, cai[0].prefix)

			amount = int(cai[0].final_number) - current_value

			self.alerts(cai[0].issue_deadline, amount)
		else:
			cai_secondary = frappe.get_all("CAI", ["initial_number", "final_number", "name_cai", "cai", "issue_deadline", "prefix"], filters = { "status": "Pending", "prefix": self.naming_series})
			
			if len(cai_secondary) > 0:
				final = int(cai[0].final_number) + 1
				initial = int(cai_secondary[0].initial_number)
				if final == initial:
					self.assing_data(cai_secondary[0].cai, cai_secondary[0].issue_deadline, cai_secondary[0].initial_number, cai_secondary[0].final_number, cai_secondary[0].prefix)
					doc = frappe.get_doc("CAI", cai[0].name_cai)
					doc.status = "Inactive"
					doc.save()

					doc_sec = frappe.get_doc("CAI", cai_secondary[0].name_cai)
					doc_sec.status = "Active"
					doc_sec.save()

					new_current = int(cai_secondary[0].initial_number) - 1
					name = self.parse_naming_series(cai_secondary[0].prefix)

					frappe.db.set_value("Series", name, "current", new_current, update_modified=False)
				else:
					self.assing_data(cai[0].cai, cai[0].issue_deadline, cai[0].initial_number, cai[0].final_number, cai[0].prefix)
					frappe.throw("The CAI you are using is expired.")
			else:
				self.assing_data(cai[0].cai, cai[0].issue_deadline, cai[0].initial_number, cai[0].final_number, cai[0].prefix)
				frappe.throw("The CAI you are using is expired.")
	
	def get_current(self, prefix):
		pre = self.parse_naming_series(prefix)
		current_value = frappe.db.get_value("Series",
		pre, "current", order_by = "name")
		return current_value

	def parse_naming_series(self, prefix):
		parts = prefix.split('.')
		if parts[-1] == "#" * len(parts[-1]):
			del parts[-1]

		pre = parse_naming_series(parts)
		return pre
	
	def assing_data(self, cai, issue_deadline, initial_number, final_number, prefix):
		pre = self.parse_naming_series(prefix)

		self.cai = cai

		self.due_date_cai = issue_deadline

		self.authorized_range = "{}{} al {}{}".format(pre, self.serie_number(int(initial_number)), pre, self.serie_number(int(final_number)))

	
	def serie_number(self, number):

		if number >= 1 and number < 10:
			return("0000000" + str(number))
		elif number >= 10 and number < 100:
			return("000000" + str(number))
		elif number >= 100 and number < 1000:
			return("00000" + str(number))
		elif number >= 1000 and number < 10000:
			return("0000" + str(number))
		elif number >= 10000 and number < 100000:
			return("000" + str(number))
		elif number >= 100000 and number < 1000000:
			return("00" + str(number))
		elif number >= 1000000 and number < 10000000:
			return("0" + str(number))
		elif number >= 10000000:
			return(str(number))
	

	def before_naming(self):
		if self.docstatus == 0:
			self.assign_cai()
	
	def alerts(self, date, amount):
		gcai_setting = frappe.get_all("Cai Settings", ["expired_days", "expired_amount"])

		if len(gcai_setting) > 0:
			if amount <= gcai_setting[0].expired_amount:
				amount_rest = amount - 1
				frappe.msgprint(_("There are only {} numbers available for this CAI.".format(amount_rest)))
		
			now = date.today()
			days = timedelta(days=int(gcai_setting[0].expired_days))

			sum_dates = now+days

			if str(date) <= str(sum_dates):
				for i in range(int(gcai_setting[0].expired_days)):		
					now1 = date.today()
					days1 = timedelta(days=i)

					sum_dates1 = now1+days1
					if str(date) == str(sum_dates1):
						frappe.msgprint(_("This CAI expires in {} days.".format(i)))
						break