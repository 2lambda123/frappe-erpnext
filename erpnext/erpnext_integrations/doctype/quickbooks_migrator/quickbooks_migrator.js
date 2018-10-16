// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('QuickBooks Migrator', {
	fetch_accounts: function(frm) {
		frappe.call({
			method: "erpnext.erpnext_integrations.doctype.quickbooks_migrator.quickbooks_migrator.get_authorization_url",
			callback: function (result) {
				console.log(result)
				if (result.message.authenticated) {
					frappe.call({
						method: "erpnext.erpnext_integrations.doctype.quickbooks_migrator.quickbooks_migrator.fetch_accounts"
					})
				} else {
					window.open(result.message.url);
				}
			}
		});
	},
	fetch_data: function(frm) {
		frappe.call({
			method: "erpnext.erpnext_integrations.doctype.quickbooks_migrator.quickbooks_migrator.get_authorization_url",
			callback: function (result) {
				console.log(result)
				if (result.message.authenticated) {
					frappe.call({
						method: "erpnext.erpnext_integrations.doctype.quickbooks_migrator.quickbooks_migrator.fetch"
					})
				} else {
					window.open(result.message.url);
				}
			}
		});
	}
});
