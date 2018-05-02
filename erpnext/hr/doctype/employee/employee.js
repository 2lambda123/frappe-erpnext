// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.hr");
erpnext.hr.EmployeeController = frappe.ui.form.Controller.extend({
	setup: function() {
		this.frm.fields_dict.user_id.get_query = function(doc, cdt, cdn) {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {ignore_user_type: 1}
			}
		}
		this.frm.fields_dict.reports_to.get_query = function(doc, cdt, cdn) {
			return { query: "erpnext.controllers.queries.employee_query"} }
	},

	refresh: function() {
		var me = this;
		erpnext.toggle_naming_series();
		frappe.ui.form.on("Employee External Work History", {
			total_experience_months: function (frm) {
				total_previous_experience(cur_frm.doc);
			}
		});
	},

	date_of_birth: function() {
		return cur_frm.call({
			method: "get_retirement_date",
			args: {date_of_birth: this.frm.doc.date_of_birth}
		});
	},

	salutation: function() {
		if(this.frm.doc.salutation) {
			this.frm.set_value("gender", {
				"Mr": "Male",
				"Ms": "Female"
			}[this.frm.doc.salutation]);
		}
	},

});
function total_previous_experience(doc){
	var total_months = 0;
	for(var i=0;i< doc.external_work_history.length;i++){
		var row = doc.external_work_history[i];
		total_months += parseFloat(row.total_experience_months);
	}
	cur_frm.set_value("total_previous_experience_months", total_months);
}

frappe.ui.form.on('Employee',{
	prefered_contact_email:function(frm){		
		frm.events.update_contact(frm)		
	},
	personal_email:function(frm){
		frm.events.update_contact(frm)
	},
	company_email:function(frm){
		frm.events.update_contact(frm)
	},
	user_id:function(frm){
		frm.events.update_contact(frm)
	},
	update_contact:function(frm){
		var prefered_email_fieldname = frappe.model.scrub(frm.doc.prefered_contact_email) || 'user_id';
		frm.set_value("prefered_email",
			frm.fields_dict[prefered_email_fieldname].value)
	},
	date_of_joining: function(frm) {
		frm.trigger("update_employee_experince");
	},
	gap: function(frm) {
		frm.trigger("update_employee_experince");
	},
	company: function(frm) {
		frm.trigger("update_employee_experince");
	},
	total_previous_experience_months: function(frm) {
		frm.trigger("update_employee_experince");
	},
	update_employee_experince: function(frm) {
		return frm.call({
			method: "get_experience",
			args: {
				company: frm.doc.company,
				date_of_joining: frm.doc.date_of_joining,
				gap: frm.doc.gap,
				previous_experience: frm.doc.total_previous_experience_months
			},
			callback: function(r)
			{
				frm.set_value("current_experience_months", r.message['current_experience']);
				frm.set_value("total_experience_months", r.message['total_experience']);
				frm.set_value("countable_experience_months", r.message['countable_experience']);
			}
		});
	},
	status: function(frm) {
		return frm.call({
			method: "deactivate_sales_person",
			args: {
				employee: frm.doc.employee,
				status: frm.doc.status
			}
		});
	},
	create_user: function(frm) {
		if (!frm.doc.prefered_email)
		{
			frappe.throw(__("Please enter Preferred Contact Email"))
		}
		frappe.call({
			method: "erpnext.hr.doctype.employee.employee.create_user",
			args: { employee: frm.doc.name, email: frm.doc.prefered_email },
			callback: function(r)
			{
				frm.set_value("user_id", r.message)
			}
		});
	}
});
cur_frm.cscript = new erpnext.hr.EmployeeController({frm: cur_frm});
