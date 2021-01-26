# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import erpnext
from frappe import _
from frappe.utils import cint, flt, getdate, today
from frappe.model.utils import get_fetch_values
from frappe.model.naming import set_name_by_naming_series
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from erpnext.accounts.party import set_contact_details, get_party_account
from erpnext.stock.get_item_details import get_item_warehouse, get_item_price, get_default_supplier
from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.setup.doctype.brand.brand import get_brand_defaults
from erpnext.setup.doctype.item_source.item_source import get_item_source_defaults
from erpnext.selling.doctype.vehicle_allocation.vehicle_allocation import get_allocation_title
from erpnext.accounts.doctype.transaction_type.transaction_type import get_transaction_type_defaults
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.vehicles.doctype.vehicle_withholding_tax_rule.vehicle_withholding_tax_rule import get_withholding_tax_amount
from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import get_terms_and_conditions
from six import string_types
import json

address_fields = ['address_line1', 'address_line2', 'city', 'state']

force_fields = [
	'customer_name', 'financer_name', 'lessee_name', 'customer_category',
	'item_name', 'item_group', 'brand',
	'address_display', 'contact_display', 'contact_email', 'contact_mobile', 'contact_phone',
	'father_name', 'husband_name',
	'tax_id', 'tax_cnic', 'tax_strn', 'tax_status', 'tax_overseas_cnic', 'passport_no',
	'withholding_tax_amount', 'exempt_from_vehicle_withholding_tax'
]
force_fields += address_fields

force_if_not_empty_fields = ['selling_transaction_type', 'buying_transaction_type',
	'receivable_account', 'payable_account']

class VehicleBookingOrder(AccountsController):
	def autoname(self):
		if self.meta.has_field('booking_number'):
			set_name_by_naming_series(self, 'booking_number')

	def validate(self):
		if self.get("_action") != "update_after_submit":
			self.set_missing_values(for_validate=True)

		self.ensure_supplier_is_not_blocked()
		self.validate_date_with_fiscal_year()

		self.validate_customer()
		self.validate_vehicle_item()
		self.validate_vehicle()
		self.validate_party_accounts()
		self.validate_allocation()
		self.validate_delivery_date()

		self.set_title()
		self.clean_remarks()

		self.calculate_taxes_and_totals()
		self.validate_amounts()
		self.validate_taxes_and_charges_accounts()
		self.set_total_in_words()

		self.get_terms_and_conditions()
		self.validate_payment_schedule()

		self.update_payment_status()
		self.update_delivery_status()
		self.update_invoice_status()
		self.set_status()

	def before_submit(self):
		self.validate_allocation_required()

	def on_submit(self):
		self.update_allocation_status()
		self.update_vehicle_status()
		self.set_status()

	def on_cancel(self):
		self.update_allocation_status()
		self.update_vehicle_status()
		self.set_status()

	def onload(self):
		if self.docstatus == 0:
			self.set_missing_values(for_validate=True)
			self.calculate_taxes_and_totals()
		elif self.docstatus == 1:
			self.set_vehicle_details()

	def before_print(self):
		super(VehicleBookingOrder, self).before_print()
		if self.docstatus == 1:
			self.set_vehicle_details()

		self.get_payment_details()

	def set_title(self):
		self.title = self.customer_name

	def get_payment_details(self):
		self.payment_received = []
		self.payment_paid = []

		if self.docstatus != 1:
			return

		payment_entries = frappe.db.sql("""
			select pe.name, pe.posting_date,
				pe.payment_type, pref.allocated_amount,
				pe.instrument_type, pe.user_remark,
				pe.reference_no, pe.reference_date, pe.deposit_no
			from `tabPayment Entry Reference` pref
			inner join `tabPayment Entry` pe on pe.name = pref.parent
			where pe.docstatus = 1
				and pref.original_reference_doctype = 'Vehicle Booking Order' and pref.original_reference_name = %s
			order by pe.reference_date, pe.posting_date, pe.creation
		""", self.name, as_dict=1)

		for d in payment_entries:
			if d.payment_type == "Receive":
				self.payment_received.append(d)

			if d.payment_type == "Pay":
				self.payment_paid.append(d)

	def validate_customer(self):
		if not self.customer and not self.customer_is_company:
			frappe.throw(_("Customer is mandatory"))

		if self.customer:
			self.validate_party()

		if self.financer and not self.finance_type:
			frappe.throw(_("Finance Type is mandatory if Financer is set"))
		if not self.financer:
			self.finance_type = ""

		if self.finance_type and self.finance_type not in ['Financed', 'Leased']:
			frappe.throw(_("Finance Type must be either 'Financed' or 'Leased'"))

	def validate_vehicle_item(self):
		item = frappe.get_cached_doc("Item", self.item_code)
		validate_vehicle_item(item)

	def validate_vehicle(self):
		if self.vehicle:
			vehicle_item_code = frappe.db.get_value("Vehicle", self.vehicle, "item_code")
			if vehicle_item_code != self.item_code:
				frappe.throw(_("Vehicle {0} is not {1}").format(self.vehicle, frappe.bold(self.item_name or self.item_code)))

			existing_filters = {"docstatus": 1, "vehicle": self.vehicle}
			if not self.is_new():
				existing_filters['name'] = ['!=', self.name]

			existing_booking = frappe.get_all("Vehicle Booking Order", filters=existing_filters, limit=1)
			existing_booking = existing_booking[0].name if existing_booking else None
			if existing_booking:
				frappe.throw(_("Cannot select Vehicle {0} because it is already ordered in {1}")
					.format(self.vehicle, existing_booking))

	def validate_allocation(self):
		self.vehicle_allocation_required = frappe.get_cached_value("Item", self.item_code, "vehicle_allocation_required")
		if not self.vehicle_allocation_required:
			self.allocation_period = ""
			self.vehicle_allocation = ""

		if self.vehicle_allocation:
			allocation_doc = frappe.get_doc("Vehicle Allocation", self.vehicle_allocation)

			self.allocation_period = allocation_doc.allocation_period
			self.delivery_period = allocation_doc.delivery_period
			self.allocation_title = get_allocation_title(allocation_doc)

			if allocation_doc.docstatus != 1:
				frappe.throw(_("Vehicle Allocation {0} ({1}) is not submitted")
					.format(self.allocation_title, self.vehicle_allocation))

			if allocation_doc.item_code != self.item_code:
				frappe.throw(_("Vehicle Allocation {0} ({1}) Vehicle Item {2} does not match Vehicle Booking Order Vehicle Item {3}")
					.format(self.allocation_title, self.vehicle_allocation,
						frappe.bold(allocation_doc.item_name or allocation_doc.item_code),
						frappe.bold(self.item_name or self.item_code)))

			if allocation_doc.supplier != self.supplier:
				frappe.throw(_("Vehicle Allocation {0} ({1}) Supplier {2} does not match Vehicle Booking Order Supplier {3}")
					.format(self.allocation_title, self.vehicle_allocation,
						frappe.bold(allocation_doc.supplier_name or allocation_doc.supplier),
						frappe.bold(self.supplier_name or self.supplier)))

			existing_filters = {"docstatus": 1, "vehicle_allocation": self.vehicle_allocation}
			if not self.is_new():
				existing_filters['name'] = ['!=', self.name]

			existing_booking = frappe.get_all("Vehicle Booking Order", filters=existing_filters, limit=1)
			existing_booking = existing_booking[0].name if existing_booking else None
			if existing_booking:
				frappe.throw(_("Cannot select Vehicle Allocation {0} ({1}) because it is already ordered in {2}")
					.format(self.allocation_title, self.vehicle_allocation, existing_booking))

		else:
			self.allocation_title = ""

	def update_vehicle_status(self):
		if self.vehicle:
			is_booked = cint(self.docstatus == 1)
			update_vehicle_booked(self.vehicle, is_booked)

	def update_allocation_status(self):
		if self.vehicle_allocation:
			is_booked = cint(self.docstatus == 1)
			update_allocation_booked(self.vehicle_allocation, is_booked)

	def validate_delivery_date(self):
		delivery_date = getdate(self.delivery_date)

		if delivery_date < getdate(self.transaction_date):
			frappe.throw(_("Delivery Due Date cannot be before Booking Date"))

		if self.delivery_period:
			from_date, to_date = frappe.get_cached_value("Vehicle Allocation Period", self.delivery_period,
				['from_date', 'to_date'])

			if delivery_date > getdate(to_date) or delivery_date < getdate(from_date):
				frappe.throw(_("Delivery Due Date must be within Delivery Period {0} if Delivery Period is selected")
					.format(self.delivery_period))

	def validate_allocation_required(self):
		required = frappe.get_cached_value("Item", self.item_code, "vehicle_allocation_required")
		if required and not self.delivery_period:
			frappe.throw(_("Delivery Period is required for allocation of {0}").format(self.item_name or self.item_code))

	def set_missing_values(self, for_validate=False):
		customer_details = get_customer_details(self.as_dict(), get_withholding_tax=False)
		for k, v in customer_details.items():
			if not self.get(k) or k in force_fields or (v and k in force_if_not_empty_fields):
				self.set(k, v)

		item_details = get_item_details(self.as_dict())
		for k, v in item_details.items():
			if not self.get(k) or k in force_fields or (v and k in force_if_not_empty_fields):
				self.set(k, v)

		self.set_vehicle_details()

	def set_vehicle_details(self, update=False):
		if self.vehicle:
			values = get_fetch_values(self.doctype, "vehicle", self.vehicle)
			if update:
				self.db_set(values)
			else:
				for k, v in values.items():
					self.set(k, v)

	def calculate_taxes_and_totals(self):
		self.round_floats_in(self, ['vehicle_amount', 'fni_amount', 'withholding_tax_amount'])

		self.invoice_total = flt(self.vehicle_amount + self.fni_amount + self.withholding_tax_amount,
			self.precision('invoice_total'))

		if self.docstatus == 0:
			self.customer_advance = 0
			self.supplier_advance = 0
			self.customer_outstanding = self.invoice_total
			self.supplier_outstanding = self.invoice_total

		self.calculate_contribution()

	def calculate_contribution(self):
		total = 0.0
		sales_team = self.get("sales_team", [])
		for sales_person in sales_team:
			self.round_floats_in(sales_person)

			sales_person.allocated_amount = flt(
				self.invoice_total * sales_person.allocated_percentage / 100.0,
				self.precision("allocated_amount", sales_person))

			total += sales_person.allocated_percentage

		if sales_team and total != 100.0:
			frappe.throw(_("Total allocated percentage for sales team should be 100"))

	def validate_amounts(self):
		for field in ['vehicle_amount', 'invoice_total']:
			self.validate_value(field, '>', 0)
		for field in ['fni_amount']:
			self.validate_value(field, '>=', 0)

	def set_total_in_words(self):
		from frappe.utils import money_in_words
		self.in_words = money_in_words(self.invoice_total, self.company_currency)

	def validate_payment_schedule(self):
		self.validate_payment_schedule_dates()
		self.set_due_date()
		self.set_payment_schedule()
		self.validate_payment_schedule_amount()
		self.validate_due_date()

	def get_terms_and_conditions(self):
		if self.tc_name:
			self.terms = get_terms_and_conditions(self.tc_name, self.as_dict())

	def validate_party_accounts(self):
		company_currency = erpnext.get_company_currency(self.company)
		receivable_currency, receivable_type = frappe.db.get_value('Account', self.receivable_account, ['account_currency', 'account_type'])
		payable_currency, payable_type = frappe.db.get_value('Account', self.payable_account, ['account_currency', 'account_type'])

		if company_currency != receivable_currency:
			frappe.throw(_("Receivable account currency should be same as company currency {0}")
				.format(company_currency))
		if company_currency != payable_currency:
			frappe.throw(_("Payable account currency should be same as company currency {0}")
				.format(company_currency))
		if receivable_type != 'Receivable':
			frappe.throw(_("Receivable Account must be of type Receivable"))
		if payable_type != 'Payable':
			frappe.throw(_("Payable Account must be of type Payable"))

	def validate_taxes_and_charges_accounts(self):
		pass
		# if self.fni_amount and not self.fni_account:
		# 	frappe.throw(_("Freight and Insurance Amount is set but account is not provided"))
		# if self.withholding_tax_amount and not self.withholding_tax_account:
		# 	frappe.throw(_("Withholding Tax Amount is set but account is not provided"))

	def update_payment_status(self, update=False):
		self.customer_outstanding = flt(self.invoice_total - self.customer_advance, self.precision('customer_outstanding'))
		self.supplier_outstanding = flt(self.invoice_total - self.supplier_advance, self.precision('supplier_outstanding'))

		if self.customer_outstanding < 0:
			frappe.throw(_("Customer Advance Received cannot be greater than the Invoice Total"))
		if self.supplier_outstanding < 0:
			frappe.throw(_("Supplier Advance Paid cannot be greater than the Invoice Total"))

		if self.customer_outstanding > 0:
			if getdate(today()) > getdate(self.due_date):
				self.customer_payment_status = "Overdue"
			elif self.customer_advance == 0:
				self.customer_payment_status = "Unpaid"
			else:
				self.customer_payment_status = "Partially Paid"
		else:
			self.customer_payment_status = "Paid"

		if self.supplier_outstanding > 0:
			if getdate(today()) > getdate(self.due_date):
				self.supplier_payment_status = "Overdue"
			elif self.supplier_advance == 0:
				self.supplier_payment_status = "Unpaid"
			else:
				self.supplier_payment_status = "Partially Paid"
		else:
			self.supplier_payment_status = "Paid"

		if update:
			self.db_set({
				'customer_outstanding': self.customer_outstanding,
				'supplier_outstanding': self.supplier_outstanding,
				'customer_payment_status': self.customer_payment_status,
				'supplier_payment_status': self.supplier_payment_status,
			})

	def update_delivery_status(self, update=False):
		purchase_receipt = None
		delivery_note = None

		if self.docstatus != 0:
			purchase_receipt = frappe.db.get_all("Purchase Receipt", {"vehicle_booking_order": self.name, "docstatus": 1},
				['name', 'posting_date', 'supplier_delivery_note'])
			delivery_note = frappe.db.get_all("Delivery Note", {"vehicle_booking_order": self.name, "docstatus": 1},
				['name', 'posting_date'])

			if len(purchase_receipt) > 1:
				frappe.throw(_("Purchase Receipt already exists against Vehicle Booking Order"))
			if len(delivery_note) > 1:
				frappe.throw(_("Delivery Note already exists against Vehicle Booking Order"))

		purchase_receipt = purchase_receipt[0] if purchase_receipt else frappe._dict()
		delivery_note = delivery_note[0] if delivery_note else frappe._dict()

		if purchase_receipt and not purchase_receipt.supplier_delivery_note:
			frappe.throw(_("Supplier Delivery Note is mandatory for Purchase receipt against Vehicle Booking Order"))

		self.vehicle_received_date = purchase_receipt.posting_date
		self.vehicle_delivered_date = delivery_note.posting_date
		self.supplier_delivery_note = purchase_receipt.supplier_delivery_note

		if not purchase_receipt:
			self.delivery_status = "To Receive"
		elif not delivery_note:
			self.delivery_status = "To Deliver"
		else:
			self.delivery_status = "Delivered"

		if update:
			self.db_set({
				"vehicle_received_date": self.vehicle_received_date,
				"vehicle_delivered_date": self.vehicle_delivered_date,
				"supplier_delivery_note": self.supplier_delivery_note,
				"delivery_status": self.delivery_status
			})

	def update_invoice_status(self, update=False):
		purchase_invoice = None
		sales_invoice = None

		if self.docstatus != 0:
			purchase_invoice = frappe.db.get_all("Purchase Invoice", {"vehicle_booking_order": self.name, "docstatus": 1},
				['name', 'posting_date', 'bill_no', 'bill_date'])
			sales_invoice = frappe.db.get_all("Sales Invoice", {"vehicle_booking_order": self.name, "docstatus": 1},
				['name', 'posting_date'])

			if len(purchase_invoice) > 1:
				frappe.throw(_("Purchase Invoice already exists against Vehicle Booking Order"))
			if len(sales_invoice) > 1:
				frappe.throw(_("Sales Invoice already exists against Vehicle Booking Order"))

			if sales_invoice and not purchase_invoice:
				frappe.throw(_("Cannot make Sales Invoice against Vehicle Booking Order before making Purchase Invoice"))

		purchase_invoice = purchase_invoice[0] if purchase_invoice else frappe._dict()
		sales_invoice = sales_invoice[0] if sales_invoice else frappe._dict()

		if purchase_invoice and (not purchase_invoice.bill_no or not purchase_invoice.bill_date):
			frappe.throw(_("Supplier Invoice No and Supplier Invoice Date is mandatory for Purchase Invoice against Vehicle Booking Order"))

		self.invoice_received_date = purchase_invoice.posting_date
		self.invoice_delivered_date = sales_invoice.posting_date
		self.bill_no = purchase_invoice.bill_no
		self.bill_date = purchase_invoice.bill_date

		if not purchase_invoice:
			self.invoice_status = "To Receive"
		elif not sales_invoice:
			self.invoice_status = "To Deliver"
		else:
			self.invoice_status = "Delivered"

		if update:
			self.db_set({
				"invoice_received_date": self.invoice_received_date,
				"invoice_delivered_date": self.invoice_delivered_date,
				"bill_no": self.bill_no,
				"bill_date": self.bill_date,
				"invoice_status": self.invoice_status
			})

	def set_status(self, update=False, status=None, update_modified=True):
		if self.is_new():
			if self.get('amended_from'):
				self.status = 'Draft'
			return

		previous_status = self.status

		if self.docstatus == 2:
			self.status = "Cancelled"

		elif self.docstatus == 1:
			if self.customer_outstanding > 0 or self.supplier_outstanding > 0:
				if self.customer_advance > self.supplier_advance:
					self.status = "To Deposit Payment"
				else:
					self.status = "To Receive Payment"

			elif self.delivery_status == "To Receive":
				self.status = "To Receive Vehicle"

			elif self.invoice_status == "To Receive":
				self.status = "To Receive Invoice"

			elif self.delivery_status == "To Deliver":
				self.status = "To Deliver Vehicle"

			elif self.invoice_status == "To Deliver":
				self.status = "To Deliver Invoice"

			else:
				self.status = "Completed"

		else:
			self.status = "Draft"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)


@frappe.whitelist()
def get_customer_details(args, get_withholding_tax=True):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)
	args.customer_is_company = cint(args.customer_is_company)

	if not args.company:
		frappe.throw(_("Company is mandatory"))
	if not args.customer and not args.customer_is_company:
		frappe.throw(_("Customer is mandatory"))
	if args.customer and args.financer and args.customer == args.financer:
		frappe.throw(_("Customer and Financer cannot be the same"))

	out = frappe._dict()

	if args.customer_is_company:
		out.customer = None

	# Determine company or customer and financer
	party_type = "Company" if args.customer_is_company else "Customer"
	party_name = args.company if args.customer_is_company else args.customer
	party = frappe.get_cached_doc(party_type, party_name)
	financer = frappe.get_cached_doc("Customer", args.financer) if args.financer else frappe._dict()
	args.finance_type = args.finance_type or 'Financed' if financer else None

	# Customer and Financer Name
	if party_type == "Customer":
		out.customer_name = party.customer_name
	else:
		out.customer_name = args.company

	if financer:
		out.financer_name = financer.customer_name
		out.lessee_name = out.customer_name

		if args.finance_type == 'Financed':
			out.customer_name = "{0} HPA {1}".format(out.customer_name, financer.customer_name)
		elif args.finance_type == 'Leased':
			out.customer_name = financer.customer_name
	else:
		out.lessee_name = None
		out.financer_name = None

	# Customer Category
	if party.get('customer_type') == "Individual":
		if args.financer:
			out.customer_category = "Lease" if args.finance_type == "Leased" else "Finance"
		else:
			out.customer_category = "Individual"
	else:
		if args.financer:
			out.customer_category = "Corporate Lease" if args.finance_type == "Leased" else "Finance"
		else:
			out.customer_category = "Corporate"

	use_financer_contact = financer and args.finance_type == "Leased"

	# Tax IDs
	out.tax_id = financer.get('tax_id') if financer else party.get('tax_id')
	out.tax_strn = financer.get('tax_strn') if financer else party.get('tax_strn')

	out.tax_cnic = party.get('tax_cnic')
	out.tax_overseas_cnic = party.get('tax_overseas_cnic')
	out.passport_no = party.get('passport_no')

	out.tax_status = financer.get('tax_status') if use_financer_contact else party.get('tax_status')

	# Additional information from custom fields
	out.father_name = party.get('father_name')
	out.husband_name = party.get('husband_name')

	# Address
	out.customer_address = args.customer_address
	if not out.customer_address:
		out.customer_address = get_default_address("Customer", financer.name) if use_financer_contact\
			else get_default_address(party_type, party_name)

	if out.customer_address:
		out.update(get_address_details(out.customer_address))
	else:
		out.address_display = None
		for f in address_fields:
			out[f] = None

	# Contact
	if use_financer_contact:
		set_contact_details(out, financer, "Customer")
	else:
		set_contact_details(out, party, party_type)

	vehicles_settings = frappe.get_cached_doc("Vehicles Settings", None)

	# Transaction Type
	out.selling_transaction_type = vehicles_settings.selling_transaction_type_company if args.customer_is_company \
		else vehicles_settings.selling_transaction_type_customer
	out.buying_transaction_type = vehicles_settings.buying_transaction_type_company if args.customer_is_company \
		else vehicles_settings.buying_transaction_type_customer

	out.receivable_account = get_party_account("Customer", None if args.customer_is_company else args.customer,
		args.company, transaction_type=out.selling_transaction_type)
	out.payable_account = get_party_account("Supplier", args.supplier,
		args.company, transaction_type=out.buying_transaction_type)

	if out.selling_transaction_type:
		out.selling_mode_of_payment = frappe.get_cached_value("Transaction Type", out.selling_transaction_type, "mode_of_payment")
	if out.buying_transaction_type:
		out.buying_mode_of_payment = frappe.get_cached_value("Transaction Type", out.buying_transaction_type, "mode_of_payment")

	# selling_vehicle_booking_defaults = get_transaction_type_defaults(out.selling_transaction_type, args.company,
	# 	fieldname='vehicle_booking_defaults')
	# buying_vehicle_booking_defaults = get_transaction_type_defaults(out.buying_transaction_type, args.company,
	# 	fieldname='vehicle_booking_defaults')
	#
	# out.fni_account = buying_vehicle_booking_defaults.get('fni_account') or selling_vehicle_booking_defaults.get('fni_account')
	# out.withholding_tax_account = buying_vehicle_booking_defaults.get('withholding_tax_account') or \
	# 	selling_vehicle_booking_defaults.get('withholding_tax_account')

	# Withholding Tax
	if get_withholding_tax and args.item_code:
		out.exempt_from_vehicle_withholding_tax = cint(frappe.get_cached_value("Item", args.item_code, "exempt_from_vehicle_withholding_tax"))

		out.withholding_tax_amount = get_withholding_tax_amount(args.transaction_date, args.item_code, out.tax_status, args.company)

	# Warehouse
	if args.item_code and (out.buying_transaction_type or out.selling_transaction_type):
		item = frappe.get_cached_doc("Item", args.item_code)
		transaction_type_defaults = get_transaction_type_defaults(out.buying_transaction_type or out.selling_transaction_type, args.company)
		out.warehouse = get_item_warehouse(item, args, overwrite_warehouse=True,
			transaction_type_defaults=transaction_type_defaults)

	return out


@frappe.whitelist()
def get_address_details(address):
	out = frappe._dict()

	address_dict = frappe.db.get_value("Address", address, "*", as_dict=True, cache=True) or {}
	out.address_display = get_address_display(address_dict)

	for f in address_fields:
		out[f] = address_dict.get(f)

	return out

@frappe.whitelist()
def get_item_details(args):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)

	if not args.company:
		frappe.throw(_("Company is mandatory"))
	if not args.item_code:
		frappe.throw(_("Vehicle Item Code is mandatory"))

	out = frappe._dict()

	item = frappe.get_cached_doc("Item", args.item_code)
	validate_vehicle_item(item)

	out.item_name = item.item_name
	out.item_group = item.item_group
	out.brand = item.brand

	item_defaults = get_item_defaults(item.name, args.company)
	item_group_defaults = get_item_group_defaults(item.name, args.company)
	brand_defaults = get_brand_defaults(item.name, args.company)
	item_source_defaults = get_item_source_defaults(item.name, args.company)
	transaction_type = args.buying_transaction_type or args.selling_transaction_type
	transaction_type_defaults = get_transaction_type_defaults(transaction_type, args.company)

	if not args.supplier:
		out.supplier = get_default_supplier(args, item_defaults, item_group_defaults, brand_defaults, item_source_defaults,
			transaction_type_defaults)

	out.warehouse = get_item_warehouse(item, args, overwrite_warehouse=True, item_defaults=item_defaults, item_group_defaults=item_group_defaults,
		brand_defaults=brand_defaults, item_source_defaults=item_source_defaults, transaction_type_defaults=transaction_type_defaults)

	out.vehicle_price_list = args.vehicle_price_list or get_default_price_list(item, args, item_defaults=item_defaults, item_group_defaults=item_group_defaults,
		brand_defaults=brand_defaults, item_source_defaults=item_source_defaults, transaction_type_defaults=transaction_type_defaults)

	fni_price_list_settings = frappe.get_cached_value("Vehicles Settings", None, "fni_price_list")
	if fni_price_list_settings:
		out.fni_price_list = fni_price_list_settings

	if args.customer:
		args.tax_status = frappe.get_cached_value("Customer", args.customer, "tax_status")

	out.exempt_from_vehicle_withholding_tax = cint(item.exempt_from_vehicle_withholding_tax)

	if out.vehicle_price_list:
		out.update(get_vehicle_price(item.name, out.vehicle_price_list, out.fni_price_list, args.transaction_date, args.tax_status, args.company))

	if not args.tc_name:
		out.tc_name = frappe.get_cached_value("Vehicles Settings", None, "default_booking_terms")

	return out


@frappe.whitelist()
def get_vehicle_default_supplier(item_code, company):
	if not company:
		frappe.throw(_("Company is mandatory"))
	if not item_code:
		frappe.throw(_("Vehicle Item Code is mandatory"))

	item = frappe.get_cached_doc("Item", item_code)

	item_defaults = get_item_defaults(item.name, company)
	item_group_defaults = get_item_group_defaults(item.name, company)
	brand_defaults = get_brand_defaults(item.name, company)
	item_source_defaults = get_item_source_defaults(item.name, company)

	default_supplier = get_default_supplier(frappe._dict({"item_code": item_code, "company": company}),
		item_defaults, item_group_defaults, brand_defaults, item_source_defaults, {})

	return default_supplier


def get_vehicle_price(item_code, vehicle_price_list, fni_price_list, transaction_date, tax_status, company):
	if not item_code:
		frappe.throw(_("Vehicle Item Code is mandatory"))
	if not vehicle_price_list:
		frappe.throw(_("Vehicle Price List is mandatory for Vehicle Price"))

	transaction_date = getdate(transaction_date)
	item = frappe.get_cached_doc("Item", item_code)

	out = frappe._dict()
	vehicle_price_args = {
		"price_list": vehicle_price_list,
		"transaction_date": transaction_date,
		"uom": item.stock_uom
	}

	vehicle_item_price = get_item_price(vehicle_price_args, item_code, ignore_party=True)
	vehicle_item_price = vehicle_item_price[0][1] if vehicle_item_price else 0
	out.vehicle_amount = flt(vehicle_item_price)

	out.withholding_tax_amount = get_withholding_tax_amount(transaction_date, item_code, tax_status, company)

	if fni_price_list:
		fni_price_args = vehicle_price_args.copy()
		fni_price_args['price_list'] = fni_price_list
		fni_item_price = get_item_price(fni_price_args, item_code, ignore_party=True)
		fni_item_price = fni_item_price[0][1] if fni_item_price else 0
		out.fni_amount = flt(fni_item_price)
	else:
		out.fni_amount = 0

	return out


def get_default_price_list(item, args, item_defaults, item_group_defaults, brand_defaults, item_source_defaults,
			transaction_type_defaults):
		price_list = (transaction_type_defaults.get('default_price_list')
			or item_defaults.get('default_price_list')
			or item_source_defaults.get('default_price_list')
			or brand_defaults.get('default_price_list')
			or item_group_defaults.get('default_price_list')
			or args.get('price_list')
		)

		if not price_list:
			price_list = frappe.get_cached_value("Vehicles Settings", None, "vehicle_price_list")
		if not price_list:
			price_list = frappe.get_cached_value("Buying Settings", None, "buying_price_list")
		if not price_list:
			price_list = frappe.get_cached_value("Selling Settings", None, "selling_price_list")

		return price_list


def validate_vehicle_item(item):
	from erpnext.stock.doctype.item.item import validate_end_of_life
	validate_end_of_life(item.name, item.end_of_life, item.disabled)

	if not item.is_vehicle:
		frappe.throw(_("{0} is not a Vehicle Item").format(item.item_name or item.name))
	if not item.include_in_vehicle_booking:
		frappe.throw(_("Vehicle Item {0} is not allowed for Vehicle Booking").format(item.item_name or item.name))


@frappe.whitelist()
def get_next_document(vehicle_booking_order, doctype):
	doc = frappe.get_doc("Vehicle Booking Order", vehicle_booking_order)

	if doc.docstatus != 1:
		frappe.throw(_("Vehicle Booking Order must be submitted"))

	if doctype == "Purchase Receipt":
		return get_purchase_receipt(doc)
	elif doctype == "Purchase Invoice":
		return get_purchase_invoice(doc)
	elif doctype == "Delivery Note":
		return get_delivery_note(doc)
	elif doctype == "Sales Invoice":
		return get_sales_invoice(doc)
	else:
		frappe.throw(_("Invalid DocType"))


def get_purchase_receipt(source):
	check_if_doc_exists("Purchase Receipt", source.name)

	target = frappe.new_doc("Purchase Receipt")

	vehicle_item = set_next_document_values(source, target, 'buying')
	prev_doc, prev_vehicle_item = get_previous_doc("Purchase Order", source)

	if prev_vehicle_item:
		vehicle_item.purchase_order = prev_vehicle_item.parent
		vehicle_item.purchase_order_item = prev_vehicle_item.name

	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	return target


def get_purchase_invoice(source):
	check_if_doc_exists("Purchase Invoice", source.name)

	target = frappe.new_doc("Purchase Invoice")

	vehicle_item = set_next_document_values(source, target, 'buying')
	prev_doc, prev_vehicle_item = get_previous_doc("Purchase Receipt", source)

	if not prev_doc:
		frappe.throw(_("Cannot make Purchase Invoice against Vehicle Booking Order before making Purchase Receipt"))

	if prev_vehicle_item:
		vehicle_item.purchase_receipt = prev_vehicle_item.parent
		vehicle_item.pr_detail = prev_vehicle_item.name

	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	return target


def get_delivery_note(source):
	check_if_doc_exists("Delivery Note", source.name)

	target = frappe.new_doc("Delivery Note")
	set_next_document_values(source, target, 'selling')
	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	return target


def get_sales_invoice(source):
	check_if_doc_exists("Sales Invoice", source.name)

	target = frappe.new_doc("Sales Invoice")

	vehicle_item = set_next_document_values(source, target, 'selling')
	prev_doc, prev_vehicle_item = get_previous_doc("Delivery Note", source)

	if not prev_doc:
		frappe.throw(_("Cannot make Sales Invoice against Vehicle Booking Order before making Delivery Note"))

	if prev_vehicle_item:
		vehicle_item.delivery_note = prev_vehicle_item.parent
		vehicle_item.dn_detail = prev_vehicle_item.name

	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	return target


def check_if_doc_exists(doctype, vehicle_booking_order):
	existing = frappe.db.get_value(doctype, {"vehicle_booking_order": vehicle_booking_order, "docstatus": ["<", 2]})
	if existing:
		frappe.throw(_("{0} already exists").format(frappe.get_desk_link(doctype, existing)))


def get_previous_doc(doctype, source):
	prev_docname = frappe.db.get_value(doctype, {"vehicle_booking_order": source.name, "docstatus": 1})
	if not prev_docname:
		return None, None

	prev_doc = frappe.get_doc(doctype, prev_docname)

	vehicle_item = prev_doc.get('items', filters={'item_code': source.item_code})
	vehicle_item = vehicle_item[0] if vehicle_item else None

	if not vehicle_item:
		frappe.throw(_("{0} {1} does not have Vehicle Item {2}").format(doctype, prev_docname, source.item_name or source.item_code))

	return prev_doc, vehicle_item


def set_next_document_values(source, target, buying_or_selling):
	if not source.vehicle and target.doctype != 'Purchase Order':
		frappe.throw(_("Please set Vehicle first"))
	if source.vehicle_allocation_required and not source.vehicle_allocation and target.doctype != 'Purchase Order':
		frappe.throw(_("Please set Vehicle Allocation first"))

	target.vehicle_booking_order = source.name
	target.company = source.company
	target.ignore_pricing_rule = 1

	if buying_or_selling == "buying":
		target.supplier = source.supplier
		target.transaction_type = source.buying_transaction_type
		target.buying_price_list = source.vehicle_price_list
	else:
		target.customer = source.customer
		target.transaction_type = source.selling_transaction_type
		target.selling_price_list = source.vehicle_price_list
		target.customer_address = source.customer_address
		target.contact_person = source.contact_person

		if source.financer and target.meta.has_field('bill_to'):
			target.bill_to = source.financer
		if target.meta.has_field('has_stin'):
			target.has_stin = 0

		for d in source.sales_team:
			target.append('sales_team', {
				'sales_person': d.sales_person, 'allocated_percentage': d.allocated_percentage
			})

	if target.meta.has_field('debit_to'):
		target.debit_to = source.receivable_account
	if target.meta.has_field('credit_to'):
		target.credit_to = source.payable_account

	vehicle_item = target.append('items')
	vehicle_item.item_code = source.item_code
	vehicle_item.qty = 1
	vehicle_item.vehicle = source.vehicle
	vehicle_item.price_list_rate = source.vehicle_amount
	vehicle_item.rate = source.invoice_total
	vehicle_item.margin_type = "Amount"
	# vehicle_item.discount_percentage = 0

	# if source.fni_amount:
	# 	add_taxes_and_charges_row(target, source.fni_account, source.fni_amount)
	# if source.withholding_tax_amount:
	# 	add_taxes_and_charges_row(target, source.withholding_tax_account, source.withholding_tax_amount)

	return vehicle_item


def add_taxes_and_charges_row(target, account, amount):
	row = target.append('taxes')

	row.charge_type = 'Actual'
	row.account_head = account
	row.tax_amount = amount

	if row.meta.has_field('category'):
		row.category = 'Valuation and Total'

	if row.meta.has_field('add_deduct_tax'):
		row.add_deduct_tax = 'Add'


@frappe.whitelist()
def update_vehicle_in_booking(vehicle_booking_order, vehicle):
	if not vehicle:
		frappe.throw(_("Vehicle not provided"))

	vbo_doc = frappe.get_doc("Vehicle Booking Order", vehicle_booking_order)
	vbo_doc._doc_before_save = frappe.get_doc(vbo_doc.as_dict())

	if vbo_doc.docstatus != 1:
		frappe.throw(_("Vehicle Booking Order {0} is not submitted").format(vehicle_booking_order))

	if vehicle == vbo_doc.vehicle:
		frappe.throw(_("Vehicle {0} is already selected in {1}").format(vehicle, vehicle_booking_order))

	if vbo_doc.delivery_status != 'To Receive':
		frappe.throw(_("Cannot change Vehicle in Vehicle Booking Order {0} because Vehicle is already received")
			.format(frappe.bold(vehicle_booking_order)))

	previous_vehicle = vbo_doc.vehicle

	vbo_doc.vehicle = vehicle
	vbo_doc.validate_vehicle_item()
	vbo_doc.validate_vehicle()
	vbo_doc.set_vehicle_details()

	vbo_doc.db_update()
	vbo_doc.notify_update()
	vbo_doc.save_version()

	update_vehicle_booked(vehicle, 1)
	if previous_vehicle:
		update_vehicle_booked(previous_vehicle, 0)

	frappe.msgprint(_("Vehicle Changed Successfully"), indicator='green', alert=True)


@frappe.whitelist()
def update_allocation_in_booking(vehicle_booking_order, vehicle_allocation):
	if not vehicle_allocation:
		frappe.throw(_("Vehicle Allocation not provided"))

	vbo_doc = frappe.get_doc("Vehicle Booking Order", vehicle_booking_order)
	vbo_doc._doc_before_save = frappe.get_doc(vbo_doc.as_dict())

	if vbo_doc.docstatus != 1:
		frappe.throw(_("Vehicle Booking Order {0} is not submitted").format(vehicle_booking_order))

	if not vbo_doc.vehicle_allocation_required:
		frappe.throw(_("Vehicle Allocation is not required in {0}").format(vehicle_booking_order))

	if vehicle_allocation == vbo_doc.vehicle_allocation:
		frappe.throw(_("Vehicle Allocation {0} is already selected in {1}").format(vehicle_allocation, vehicle_booking_order))

	if vbo_doc.delivery_status != 'To Receive':
		frappe.throw(_("Cannot change Vehicle Allocation in Vehicle Booking Order {0} because Vehicle is already received")
			.format(frappe.bold(vehicle_booking_order)))

	if flt(vbo_doc.supplier_advance):
		frappe.throw(_("Cannot change Vehicle Allocation in Vehicle Booking Order {0}  because Supplier Payment has already been made")
			.format(frappe.bold(vehicle_booking_order)))

	previous_allocation = vbo_doc.vehicle_allocation

	vbo_doc.vehicle_allocation = vehicle_allocation
	vbo_doc.validate_allocation()

	if vbo_doc.delivery_period != vbo_doc._doc_before_save.delivery_period:
		frappe.throw(_("Delivery Period must be the same in the new Vehicle Allocation"))

	vbo_doc.db_update()
	vbo_doc.notify_update()
	vbo_doc.save_version()

	update_allocation_booked(vehicle_allocation, 1)
	if previous_allocation:
		update_allocation_booked(previous_allocation, 0)

	frappe.msgprint(_("Allocation Changed Successfully"), indicator='green', alert=True)


def update_vehicle_booked(vehicle, is_booked):
	is_booked = cint(is_booked)
	frappe.db.set_value("Vehicle", vehicle, "is_booked", is_booked, notify=True)


def update_allocation_booked(vehicle_allocation, is_booked):
	is_booked = cint(is_booked)
	frappe.db.set_value("Vehicle Allocation", vehicle_allocation, "is_booked", is_booked, notify=True)
