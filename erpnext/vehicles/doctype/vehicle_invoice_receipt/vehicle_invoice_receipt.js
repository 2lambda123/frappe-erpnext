// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("erpnext.vehicles");
erpnext.vehicles.VehicleInvoiceReceiptController = erpnext.vehicles.VehicleTransactionController.extend({
	setup_queries: function () {
		this._super();

		var me = this;
		this.frm.set_query("vehicle", function () {
			var filters = {
				item_code: me.frm.doc.item_code
			};

			if (me.frm.doc.supplier) {
				filters['supplier'] = ['in', ['', me.frm.doc.supplier]];
			}

			return {
				filters: filters
			}
		});

		this.frm.set_query("vehicle_booking_order", function() {
			return {
				filters: {
					docstatus: 1,
					status: ['!=', 'Cancelled Booking'],
					invoice_status: 'To Receive',
					vehicle: ['is', 'set']
				}
			};
		});
	}
});

$.extend(cur_frm.cscript, new erpnext.vehicles.VehicleInvoiceReceiptController({frm: cur_frm}));
