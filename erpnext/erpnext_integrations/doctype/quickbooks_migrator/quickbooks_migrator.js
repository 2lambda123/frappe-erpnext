// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('QuickBooks Migrator', {
	connect: function(frm) {
		// OAuth requires user intervention to provide application access permissionsto requested scope
		// Here we open a new window and redirect user to the authorization url.
		// After user grants us permission to access. We will set authorization details on this doc which will force refresh.
		window.open(frm.doc.authorization_url)
	},
	fetch_data: function(frm) {
		frm.call("migrate")
	},
	onload: function(frm) {
		// Instead of changing percentage width and message of single progress bar
		// Show a different porgress bar for every action after some time remove the finished progress bar
 		// Former approach causes the progress bar to dance back and forth.
		frm.dashboard.hide_progress = frappe.utils.debounce(frm.dashboard.hide_progress, 1000)
 		frappe.realtime.on("quickbooks_progress_update", function (data) {
			if (data.event == "finish") {
				frm.dashboard.hide_progress(data.message)
			}
			else if (data.event == "progress") {
				frm.dashboard.show_progress(data.message, (data.count / data.total) * 100, data.message)
			}
		});
	},
	refresh: function(frm){
		if (!frm.doc.access_token) {
			// Unset access_token signifies that we don't have enough information to connect to quickbooks api and fetch data
			if (frm.doc.authorization_url) {
				frm.add_custom_button(__("Connect to Quickbooks"), function () {
					frm.trigger("connect")
				});
			}
		}
		if (frm.doc.access_token) {
			// If we have access_token that means we also have refresh_token we don't need user intervention anymore
			// All we need now is a Company from erpnext
			frm.remove_custom_button(__("Connect to Quickbooks"))

			frm.toggle_display("company_settings", 1)
			frm.set_df_property("company", "reqd", 1)
			frm.add_custom_button(__("Fetch Data"), function () {
				frm.trigger("fetch_data")
			});
		}
	}
});
