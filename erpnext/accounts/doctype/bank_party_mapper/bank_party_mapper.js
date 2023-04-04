// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Party Mapper", {
	refresh(frm) {
        if (!frm.is_new()) {
            frm.set_intro(__("Please avoid editing unless you are absolutely certain."));
        }
	},
});
