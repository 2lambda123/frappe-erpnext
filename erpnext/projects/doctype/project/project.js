// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
frappe.ui.form.on("Project", {
	setup: function(frm) {
		frm.make_methods = {
			'Timesheet': () => {
				open_form(frm, "Timesheet", "Timesheet Detail", "time_logs");
			},
			'Purchase Order': () => {
				open_form(frm, "Purchase Order", "Purchase Order Item", "items");
			},
			'Purchase Receipt': () => {
				open_form(frm, "Purchase Receipt", "Purchase Receipt Item", "items");
			},
			'Purchase Invoice': () => {
				open_form(frm, "Purchase Invoice", "Purchase Invoice Item", "items");
			},
		};

		frm.custom_make_buttons = {};
		frm.make_button_dts = [
			'Quotation', 'Sales Order', 'Delivery Note', 'Sales Invoice',
			'Maintenance Visit', 'Warranty Claim', 'Quality Inspection',
			'Stock Entry'
		];
		$.each(frm.make_button_dts, function (i, dt) {
			frm.custom_make_buttons[dt] = __(dt);
		});

		frm.set_indicator_formatter('title',
			function (doc) {
				let indicator = 'orange';
				if (doc.status == 'Overdue') {
					indicator = 'red';
				} else if (doc.status == 'Cancelled') {
					indicator = 'dark grey';
				} else if (doc.status == 'Closed') {
					indicator = 'green';
				}
				return indicator;
			}
		);
	},
	onload: function (frm) {
		var so = frappe.meta.get_docfield("Project", "sales_order");
		so.get_route_options_for_new_doc = function (field) {
			if (frm.is_new()) return;
			return {
				"customer": frm.doc.customer,
				"project_name": frm.doc.name
			};
		};

		frm.set_query('customer', 'erpnext.controllers.queries.customer_query');
		frm.set_query('bill_to', 'erpnext.controllers.queries.customer_query');

		frm.set_query("user", "users", function () {
			return {
				query: "erpnext.projects.doctype.project.project.get_users_for_project"
			};
		});

		// sales order
		frm.set_query('sales_order', function () {
			var filters = {
				'project': ["in", frm.doc.__islocal ? [""] : [frm.doc.name, ""]]
			};

			if (frm.doc.customer) {
				filters["customer"] = frm.doc.customer;
			}

			return {
				filters: filters
			};
		});

		if(frm.fields_dict.insurance_company) {
			frm.set_query("insurance_company", function(doc) {
				return {filters: {is_insurance_company: 1}};
			});
		}
	},

	refresh: function (frm) {
		if (frappe.defaults.get_default("project_naming_by")!="Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frm.doc.__islocal) {
			frm.web_link && frm.web_link.remove();
		} else {
			frm.add_web_link("/projects?project=" + encodeURIComponent(frm.doc.name));

			frm.trigger('show_dashboard');
		}

		if (frm.fields_dict.vehicle_first_odometer && frm.fields_dict.vehicle_last_odometer) {
			var first_odometer_read_only = cint(frm.doc.vehicle_first_odometer);
			var last_odometer_read_only = !cint(frm.doc.vehicle_first_odometer) || cint(frm.doc.vehicle_last_odometer) !== cint(frm.doc.vehicle_first_odometer);
			frm.set_df_property("vehicle_first_odometer", "read_only", first_odometer_read_only);
			frm.set_df_property("vehicle_last_odometer", "read_only", last_odometer_read_only);
		}

		frm.events.setup_vehicle_route_options(frm);
		frm.events.set_buttons(frm);
	},

	set_buttons: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Duplicate Project with Tasks'), () => {
				frm.events.create_duplicate(frm);
			});

			frm.add_custom_button(__('Completed'), () => {
				frm.events.set_status(frm, 'Completed');
			}, __('Set Status'));

			frm.add_custom_button(__('Cancelled'), () => {
				frm.events.set_status(frm, 'Cancelled');
			}, __('Set Status'));
		}

		if (frappe.model.can_read("Task")) {
			frm.add_custom_button(__("Gantt Chart"), function () {
				frappe.route_options = {
					"project": frm.doc.name
				};
				frappe.set_route("List", "Task", "Gantt");
			});

			frm.add_custom_button(__("Kanban Board"), () => {
				frappe.call('erpnext.projects.doctype.project.project.create_kanban_board_if_not_exists', {
					project: frm.doc.project_name
				}).then(() => {
					frappe.set_route('List', 'Task', 'Kanban', frm.doc.project_name);
				});
			});
		}

		if (!frm.doc.__islocal) {
			var item_table_fieldnames = {
				'Maintenance Visit': 'purposes',
				'Stock Entry': 'items',
				'Delivery Note': 'items'
			};

			$.each(frm.make_button_dts, function (i, dt) {
				var items_fieldname = item_table_fieldnames[dt];

				frm.add_custom_button(__(dt), function() {
					frappe.new_doc(dt, {
						customer: frm.doc.customer,
						party: frm.doc.customer,
						party_name: frm.doc.customer,
						quotation_to: 'Customer',
						party_type: 'Customer',
						project: frm.doc.name,
						item_code: frm.doc.item_code,
						serial_no: frm.doc.serial_no,
						item_serial_no: frm.doc.serial_no
					}).then(r => {
						if (dt == "Stock Entry") {
							cur_frm.set_value('purpose', 'Material Receipt');
							cur_frm.set_value('for_maintenance', 1);
						}
						if (items_fieldname) {
							cur_frm.doc[items_fieldname] = [];
							var child = cur_frm.add_child(items_fieldname, {
								project: frm.doc.name,
								serial_no: frm.doc.serial_no
							});
							if (frm.doc.item_code) {
								frappe.model.set_value(child.doctype, child.name, 'item_code', frm.doc.item_code);
							}
						}
					});
				}, __("Make"));
			});
		}
	},

	setup_vehicle_route_options: function(frm) {
		var vehicle_field = frm.get_docfield("applies_to_vehicle");
		if (vehicle_field) {
			vehicle_field.get_route_options_for_new_doc = function () {
				return {
					"item_code": frm.doc.applies_to_item,
					"item_name": frm.doc.applies_to_item_name
				}
			}
		}
	},

	create_duplicate: function(frm) {
		return new Promise(resolve => {
			frappe.prompt('Project Name', (data) => {
				frappe.xcall('erpnext.projects.doctype.project.project.create_duplicate_project',
					{
						prev_doc: frm.doc,
						project_name: data.value
					}).then(() => {
					frappe.set_route('Form', "Project", data.value);
					frappe.show_alert(__("Duplicate project has been created"));
				});
				resolve();
			});
		});
	},

	serial_no: function (frm) {
		if (frm.doc.serial_no) {
			frappe.call({
				method: "erpnext.stock.doctype.serial_no.serial_no.get_serial_no_item_customer",
				args: {
					serial_no: frm.doc.serial_no
				},
				callback: function (r) {
					if (r.message) {
						$.each(r.message || {}, function (k, v) {
							frm.set_value(k, v);
						});
					}
				}
			})
		}
	},

	set_status: function(frm, status) {
		frappe.confirm(__('Set Project and all Tasks to status {0}?', [status.bold()]), () => {
			frappe.xcall('erpnext.projects.doctype.project.project.set_project_status',
				{project: frm.doc.name, status: status}).then(() => { /* page will auto reload */ });
		});
	},

	collect_progress: function(frm) {
		frm.set_df_property("message", "reqd", frm.doc.collect_progress);
	}
});

function open_form(frm, doctype, child_doctype, parentfield) {
	frappe.model.with_doctype(doctype, () => {
		let new_doc = frappe.model.get_new_doc(doctype);

		// add a new row and set the project
		let new_child_doc = frappe.model.get_new_doc(child_doctype);
		new_child_doc.project = frm.doc.name;
		new_child_doc.parent = new_doc.name;
		new_child_doc.parentfield = parentfield;
		new_child_doc.parenttype = doctype;
		new_doc[parentfield] = [new_child_doc];

		frappe.ui.form.make_quick_entry(doctype, null, null, new_doc);
	});

}
