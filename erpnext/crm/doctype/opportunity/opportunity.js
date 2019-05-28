// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.crm");

cur_frm.email_field = "contact_email";
frappe.ui.form.on("Opportunity", {
	setup: function(frm) {
		frm.custom_make_buttons = {
			'Quotation': 'Quotation',
			'Supplier Quotation': 'Supplier Quotation'
		};
	},

	onload_post_render: function(frm) {
		frm.get_field("items").grid.set_multiple_add("item_code", "qty");
	},

	party_name: function(frm) {
		frm.toggle_display("contact_info", frm.doc.party_name);

		if (frm.doc.opportunity_from == "Customer") {
			frm.trigger('set_contact_link');
			erpnext.utils.get_party_details(frm);
		} else if (frm.doc.opportunity_from == "Lead") {
			erpnext.utils.map_current_doc({
				method: "erpnext.crm.doctype.lead.lead.make_opportunity",
				source_name: frm.doc.party_name,
				frm: frm
			});
		}
	},

	with_items: function(frm) {
		frm.trigger('toggle_mandatory');
	},

	customer_address: function(frm, cdt, cdn) {
		erpnext.utils.get_address_display(frm, 'customer_address', 'address_display', false);
	},

	contact_person: erpnext.utils.get_contact_details,

	opportunity_from: function(frm) {
		frm.toggle_reqd("party_name", frm.doc.opportunity_from);
		frm.trigger("set_dynamic_field_label");
	},

	refresh: function(frm) {
		var doc = frm.doc;
		frm.events.opportunity_from(frm);
		frm.trigger('toggle_mandatory');
		erpnext.toggle_naming_series();

		if(!doc.__islocal && doc.status!=="Lost") {
			if(doc.with_items){
				frm.add_custom_button(__('Supplier Quotation'),
					function() {
						frm.trigger("make_supplier_quotation")
					}, __("Make"));
			}

			frm.add_custom_button(__('Quotation'),
				cur_frm.cscript.create_quotation, __("Make"));

			if(doc.status!=="Quotation") {
				frm.add_custom_button(__('Lost'),
					cur_frm.cscript['Declare Opportunity Lost']);
			}
		}

		if(!frm.doc.__islocal && frm.perm[0].write && frm.doc.docstatus==0) {
			if(frm.doc.status==="Open") {
				frm.add_custom_button(__("Close"), function() {
					frm.set_value("status", "Closed");
					frm.save();
				});
			} else {
				frm.add_custom_button(__("Reopen"), function() {
					frm.set_value("status", "Open");
					frm.save();
				});
			}
		}
	},

	set_contact_link: function(frm) {
		if(frm.doc.opportunity_from == "Customer" && frm.doc.party_name) {
			frappe.dynamic_link = {doc: frm.doc, fieldname: 'party_name', doctype: 'Customer'}
		} else if(frm.doc.opportunity_from == "Lead" && frm.doc.party_name) {
			frappe.dynamic_link = {doc: frm.doc, fieldname: 'party_name', doctype: 'Lead'}
		}
	},

	set_dynamic_field_label: function(frm){

		if (frm.doc.opportunity_from) {
			frm.set_df_property("party_name", "label", frm.doc.opportunity_from);
		}
	},

	make_supplier_quotation: function(frm) {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_supplier_quotation",
			frm: cur_frm
		})
	},

	toggle_mandatory: function(frm) {
		frm.toggle_reqd("items", frm.doc.with_items ? 1:0);
	}
})

// TODO commonify this code
erpnext.crm.Opportunity = frappe.ui.form.Controller.extend({
	onload: function() {

		if(!this.frm.doc.status)
			set_multiple(this.frm.doc.doctype, this.frm.doc.name, { status:'Open' });
		if(!this.frm.doc.company && frappe.defaults.get_user_default("Company"))
			set_multiple(this.frm.doc.doctype, this.frm.doc.name,
				{ company:frappe.defaults.get_user_default("Company") });
		if(!this.frm.doc.currency)
			set_multiple(this.frm.doc.doctype, this.frm.doc.name, { currency:frappe.defaults.get_user_default("Currency") });

		this.setup_queries();
	},

	setup_queries: function() {
		var me = this;

		if(this.frm.fields_dict.contact_by.df.options.match(/^User/)) {
			this.frm.set_query("contact_by", erpnext.queries.user);
		}

		me.frm.set_query('customer_address', erpnext.queries.address_query);

		this.frm.set_query("item_code", "items", function() {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters: {'is_sales_item': 1}
			};
		});

		me.frm.set_query('contact_person', erpnext.queries['contact_query'])

		if (me.frm.doc.opportunity_from == "Lead") {
			me.frm.set_query('party_name', erpnext.queries['lead']);
		}
		else if (me.frm.doc.opportunity_from == "Cuatomer") {
			me.frm.set_query('party_name', erpnext.queries['customer']);
		}
	},

	create_quotation: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.crm.doctype.opportunity.opportunity.make_quotation",
			frm: cur_frm
		})
	}
});

$.extend(cur_frm.cscript, new erpnext.crm.Opportunity({frm: cur_frm}));

cur_frm.cscript.item_code = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.item_code) {
		return frappe.call({
			method: "erpnext.crm.doctype.opportunity.opportunity.get_item_details",
			args: {"item_code":d.item_code},
			callback: function(r, rt) {
				if(r.message) {
					$.each(r.message, function(k, v) {
						frappe.model.set_value(cdt, cdn, k, v);
					});
					refresh_field('image_view', d.name, 'items');
				}
			}
		})
	}
}

cur_frm.cscript['Declare Opportunity Lost'] = function() {
	var dialog = new frappe.ui.Dialog({
		title: __("Set as Lost"),
		fields: [
			{"fieldtype": "Text", "label": __("Reason for losing"), "fieldname": "reason",
				"reqd": 1 },
			{"fieldtype": "Button", "label": __("Update"), "fieldname": "update"},
		]
	});

	dialog.fields_dict.update.$input.click(function() {
		var args = dialog.get_values();
		if(!args) return;
		return cur_frm.call({
			doc: cur_frm.doc,
			method: "declare_enquiry_lost",
			args: args.reason,
			callback: function(r) {
				if(r.exc) {
					frappe.msgprint(__("There were errors."));
				} else {
					dialog.hide();
					cur_frm.refresh();
				}
			},
			btn: this
		})
	});
	dialog.show();
}
