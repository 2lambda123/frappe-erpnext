// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Workstation", {
	onload: function(frm) {
		if(frm.is_new())
		{
			frappe.call({
				type:"GET",
				method:"erpnext.manufacturing.doctype.workstation.workstation.get_default_holiday_list",
				callback: function(r) {
					if(!r.exe && r.message){
						cur_frm.set_value("holiday_list", r.message);
					}
				}
			})
		}
	}
})

frappe.tour['Workstation'] = [
	{
		fieldname: "workstation_name",
		title: "Workstation Name",
		description: __("You can set it as a machine name or operation type. For example, stiching machine 12")
	},
	{
		fieldname: "production_capacity",
		title: "Production Capacity",
		description: __("No. of parallel job cards which can be allowed on this workstation. Example: 2 would mean this workstation can process production for two Work Orders at a time.")
	},
	{
		fieldname: "working_hours_section",
		title: "Working Hours",
		description: "Enter working hours for operation"
	}
];
