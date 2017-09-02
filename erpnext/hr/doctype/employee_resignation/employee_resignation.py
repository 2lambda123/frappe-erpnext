# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import msgprint, _

class EmployeeResignation(Document):
	
	def on_submit(self):
		emp = frappe.get_doc("Employee",self.employee)
		emp.status ="Left"
		emp.relieving_date =self.permission_date
		emp.save(ignore_permissions=True)
		eos_award=frappe.new_doc("End of Service Award")
		eos_award.employee=self.employee
		eos_award.end_date=self.permission_date
		eos_award.reason="استقالة العامل"
		eos_award.insert()
	def validate(self):
		if self.workflow_state:
			if "Rejected" in self.workflow_state:
			    self.docstatus = 1
			    self.docstatus = 2

		if frappe.get_value('Employee Loan', filters={'employee' : self.employee,'status':'Sanctioned'}):
			name=frappe.get_value('Employee Loan', filters={'employee' : self.employee,'status':'Sanctioned'}) 
			loan_emp =frappe.get_doc("Employee Loan",name)		
			mm=loan_emp.status
			frappe.throw(self.employee+"/ "+self.employee_name+" have an active loan")

		#if frappe.get_value('Financial Custody', filters={'employee' : self.employee}):
			#name=frappe.get_value('Financial Custody', filters={'employee' : self.employee}) 
			#custody =frappe.get_doc("Financial Custody",name)
			#approver=custody.reported_by
			#if approver:
				#frappe.throw(self.employee+"/ "+self.employee_name+" have an active Financial Custody approved by "+approver)

		

