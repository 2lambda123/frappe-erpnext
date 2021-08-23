// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("erpnext.vehicles");

erpnext.vehicles.VehicleController = frappe.ui.form.Controller.extend({
	setup: function () {
		var me = this;

		this.frm.set_query("item_code", function() {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters: {'is_vehicle': 1}
			};
		});
		this.frm.set_query("sales_order", function() {
			return {
				filters: {'docstatus': ['!=', 2]}
			};
		});

		this.frm.set_query("insurance_company", function(doc) {
			return {filters: {is_insurance_company: 1}};
		});

		this.frm.set_query("vehicle_owner", function(doc) {
			return erpnext.queries.customer();
		});

		this.frm.set_query("reserved_customer", function(doc) {
			return erpnext.queries.customer();
		});

		this.frm.set_query("color", function() {
			return erpnext.queries.vehicle_color({item_code: me.frm.doc.item_code});
		});
	},

	refresh: function () {
		erpnext.hide_company();

		if(!this.frm.is_new()) {
			this.frm.add_custom_button(__("View Ledger"), () => {
				frappe.route_options = {
					serial_no: this.frm.doc.name,
					from_date: frappe.defaults.get_user_default("year_start_date"),
					to_date: frappe.defaults.get_user_default("year_end_date")
				};
				frappe.set_route("query-report", "Stock Ledger");
			});
		}

		const cant_change_fields = (this.frm.doc.__onload && this.frm.doc.__onload.cant_change_fields) || {};
		$.each(cant_change_fields, (fieldname, cant_change) => {
			this.frm.set_df_property(fieldname, 'read_only', cint(cant_change));
		});
	},

	unregistered: function () {
		if (this.frm.doc.unregistered) {
			this.frm.set_value("license_plate", "");
		}
	},

	chassis_no: function () {
		erpnext.utils.format_vehicle_id(this.frm, 'chassis_no');
		erpnext.utils.validate_duplicate_vehicle(this.frm.doc, 'chassis_no');
	},
	engine_no: function () {
		erpnext.utils.format_vehicle_id(this.frm, 'engine_no');
		erpnext.utils.validate_duplicate_vehicle(this.frm.doc, 'engine_no');
	},
	license_plate: function () {
		erpnext.utils.format_vehicle_id(this.frm, 'license_plate');
		erpnext.utils.validate_duplicate_vehicle(this.frm.doc, 'license_plate');
	},
});

$.extend(cur_frm.cscript, new erpnext.vehicles.VehicleController({frm: cur_frm}));