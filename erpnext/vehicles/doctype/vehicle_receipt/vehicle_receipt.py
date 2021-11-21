# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erpnext.vehicles.vehicle_transaction_controller import VehicleTransactionController

class VehicleReceipt(VehicleTransactionController):
	def get_feed(self):
		if self.get('customer'):
			return _("For {0} | {1}").format(self.get("customer_name") or self.get('customer'),
				self.get("item_name") or self.get("item_code"))
		else:
			return _("From {0} | {1}").format(self.get("suplier_name") or self.get('supplier'),
				self.get("item_name") or self.get("item_code"))

	def validate(self):
		super(VehicleReceipt, self).validate()
		self.validate_party_mandatory()
		self.set_title()

	def before_submit(self):
		self.validate_vehicle_mandatory()
		self.validate_transporter()

	def on_submit(self):
		self.update_stock_ledger()
		self.update_vehicle_warranty_no()
		self.make_odometer_log()
		self.update_vehicle_booking_order_delivery()

	def on_cancel(self):
		self.update_stock_ledger()
		self.cancel_odometer_log()
		self.update_vehicle_booking_order_delivery()

	def set_title(self):
		party = self.get('customer_name') or self.get('customer') or self.get('supplier_name') or self.get('supplier')
		self.title = "{0} - {1}".format(party, self.item_name or self.item_code)

	def validate_transporter(self):
		if self.get('transporter') and not self.get('lr_no'):
			frappe.throw(_("Transport Receipt No (Bilty) is mandatory when receiving from Transporter"))

