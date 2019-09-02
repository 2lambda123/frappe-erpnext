# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, nowdate, flt, cint

class FBRInvoiceWiseTaxes(object):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.from_date = getdate(self.filters.from_date or nowdate())
		self.filters.to_date = getdate(self.filters.to_date or nowdate())

		if not self.filters.get("company"):
			self.filters["company"] = frappe.db.get_single_value('Global Defaults', 'default_company')

		self.filters.service_tax_account = frappe.get_cached_value('Company', self.filters.company, "service_tax_account")

	def run(self, args):
		if self.filters.from_date > self.filters.to_date:
			frappe.throw(_("From Date must be before To Date"))

		self.filters.party_type = args.get("party_type")
		self.party_naming_by = frappe.db.get_value(args.get("naming_by")[0], None, args.get("naming_by")[1])

		data = self.get_data()
		columns = self.get_columns()
		return columns, data

	def get_columns(self):
		columns = [
			{
				"label": _("NTN"),
				"fieldtype": "Data",
				"fieldname": "tax_id",
				"width": 70
			},
			{
				"label": _("CNIC"),
				"fieldtype": "Data",
				"fieldname": "tax_cnic",
				"width": 110
			},
			{
				"label": _("Name of Buyer"),
				"fieldtype": "Link",
				"fieldname": "party",
				"options": self.filters.party_type,
				"width": 200
			},
			{
				"label": _("Name of Buyer"),
				"fieldtype": "Data",
				"fieldname": "party_name",
				"width": 110
			},
			{
				"label": _("District of Buyer"),
				"fieldtype": "Data",
				"fieldname": "city",
				"editable": 1,
				"width": 90
			},
			{
				"label": _("Buyer Type"),
				"fieldtype": "Data",
				"fieldname": "buyer_type",
				"width": 90
			},
			{
				"label": _("Document Type"),
				"fieldtype": "Data",
				"fieldname": "document_type",
				"width": 50,
				"hide_for_view": 1
			},
			{
				"label": _("Sales Invoice"),
				"fieldtype": "Link",
				"fieldname": "invoice",
				"options": "Sales Invoice",
				"width": 90,
				"hide_for_export": 1
			},
			{
				"label": _("Document Number"),
				"fieldtype": "Int",
				"fieldname": "stin",
				"width": 60
			},
			{
				"label": _("Document Date"),
				"fieldtype": "Data",
				"fieldname": "posting_date",
				"width": 80
			},
			{
				"label": _("HS Code"),
				"fieldtype": "Data",
				"fieldname": "hscode",
				"width": 80,
				"hide_for_view": 1
			},
			{
				"label": _("Sale Type"),
				"fieldtype": "Data",
				"fieldname": "sale_type",
				"width": 80,
				"hide_for_view": 1
			},
			{
				"label": _("Rate"),
				"fieldtype": "Percent",
				"fieldname": "rate",
				"width": 50
			},
			{
				"label": _("Value of Sales Excluding Sales Tax"),
				"fieldtype": "Currency",
				"fieldname": "base_taxable_total",
				"options": "Company:company:default_currency",
				"width": 110
			},
			{
				"label": _("Sales Tax Involved"),
				"fieldtype": "Currency",
				"fieldname": "service_tax",
				"options": "Company:company:default_currency",
				"width": 110
			},
			{
				"label": _("ST Withheld at Source"),
				"fieldtype": "Data",
				"fieldname": "withheld_amount",
				"width": 80,
				"hide_for_view": 1
			},
		]

		if self.party_naming_by != "Naming Series":
			columns = filter(lambda d: d['fieldname'] != 'party_name', columns)

		if cint(self.filters.for_export):
			columns = filter(lambda d: not d.get("hide_for_export"), columns)
		else:
			columns = filter(lambda d: not d.get("hide_for_view"), columns)

		return columns

	def get_data(self):
		conditions = "and i.customer = %(party)s" if self.filters.party else ""

		self.invoices = frappe.db.sql("""
			select
				i.name as invoice, i.stin, DATE_FORMAT(i.posting_date, '%%d/%%m/%%Y') as posting_date,
				i.base_taxable_total, i.base_grand_total, addr.city, addr.name as address_name,
				i.customer as party, i.customer_name as party_name, c.tax_id, c.tax_cnic
			from `tabSales Invoice` i
			left join `tabCustomer` c on c.name = i.customer
			left join `tabAddress` addr on addr.name = i.customer_address
			where i.docstatus = 1 and i.company = %(company)s and i.posting_date between %(from_date)s and %(to_date)s
				and ifnull(i.stin, 0) != 0 {0} and i.order_type = 'Maintenance'
			order by i.posting_date, i.stin
		""".format(conditions), self.filters, as_dict=1)

		invoices_map = {}
		for d in self.invoices:
			d.service_tax = 0
			d.buyer_type = "End_Consumer"
			d.sale_type = "Services"
			d.document_type = "SI"
			d.hscode = "98201000"
			invoices_map[d.invoice] = d

		tax_accounts = []
		if self.filters.service_tax_account:
			tax_accounts.append(self.filters.service_tax_account)

		if invoices_map and tax_accounts:
			taxes = frappe.db.sql("""
				select
					parent as invoice, rate, sum(base_tax_amount_after_discount_amount) as amount, account_head
				from `tabSales Taxes and Charges`
				where parent in ({0}) and account_head in ({1})
					and abs(base_tax_amount_after_discount_amount) > 0
				group by parent, account_head
			""".format(", ".join(['%s'] * len(invoices_map.keys())), ", ".join(['%s'] * len(tax_accounts))),
				invoices_map.keys() + tax_accounts, as_dict=1)
		else:
			taxes = []

		for tax in taxes:
			tax_field = ''
			if tax.account_head == self.filters.service_tax_account:
				tax_field = 'service_tax'
				invoices_map[tax.invoice]['rate'] = tax.rate

			if tax_field:
				invoices_map[tax.invoice][tax_field] += flt(tax.amount)

		return self.invoices


def execute(filters=None):
	args = {
		"party_type": "Customer",
		"naming_by": ["Selling Settings", "cust_master_name"],
	}
	return FBRInvoiceWiseTaxes(filters).run(args)
