// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Inpatient Medication Orders"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "patient",
			label: __("Patient"),
			fieldtype: "Link",
			options: "Patient"
		},
		{
			fieldname: "show_completed_orders",
			label: __("Show Completed Orders"),
			fieldtype: "Check",
			default: 1
		}
	]
};
