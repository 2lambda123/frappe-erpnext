// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Accounts Payable"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname":"ageing_based_on",
			"label": __("Ageing Based On"),
			"fieldtype": "Select",
			"options": 'Posting Date\nDue Date\nSupplier Invoice Date',
			"default": "Posting Date"
		},
		{
			"fieldname":"report_date",
			"label": __("As on Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname":"range1",
			"label": __("Ageing Range 1"),
			"fieldtype": "Int",
			"default": "30",
			"reqd": 1
		},
		{
			"fieldname":"range2",
			"label": __("Ageing Range 2"),
			"fieldtype": "Int",
			"default": "60",
			"reqd": 1
		},
		{
			"fieldname":"range3",
			"label": __("Ageing Range 3"),
			"fieldtype": "Int",
			"default": "90",
			"reqd": 1
		},
		{
			"fieldname":"finance_book",
			"label": __("Finance Book"),
			"fieldtype": "Link",
			"options": "Finance Book"
		},
		{
			"fieldname":"supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
			on_change: () => {
				var supplier = frappe.query_report.get_filter_value('supplier');
				if (supplier) {
					frappe.db.get_value('Supplier', supplier, "tax_id", function(value) {
						frappe.query_report.set_filter_value('tax_id', value["tax_id"]);
					});
				} else {
					frappe.query_report.set_filter_value('tax_id', "");
				}
			}
		},
		{
			"fieldname":"supplier_group",
			"label": __("Supplier Group"),
			"fieldtype": "Link",
			"options": "Supplier Group"
		},
		{
			"fieldname":"cost_center",
			"label": __("Cost Center"),
			"fieldtype": "Link",
			"options": "Cost Center"
		},
		{
			"fieldname":"group_by",
			"label": __("Group By"),
			"fieldtype": "Select",
			"options": "Ungrouped\nGroup by Supplier\nGroup by Supplier Group",
			"default": "Ungrouped"
		},
		{
			"fieldname":"mark_overdue_in_print",
			"label": __("Mark Overdue in Print"),
			"fieldtype": "Check",
			on_change: function() { return false; }
		},
		{
			"fieldname":"tax_id",
			"label": __("NTN"),
			"fieldtype": "Data",
			"hidden": 1
		}
	],
	onload: function(report) {
		report.page.add_inner_button(__("Accounts Payable Summary"), function() {
			var filters = report.get_values();
			frappe.set_route('query-report', 'Accounts Payable Summary', {company: filters.company});
		});
	},

	get_datatable_options(options) {
		return Object.assign(options, {
			hooks: {
				columnTotal: function(values, column) {
					const me = this;
					values = values.filter((d, i) => {
						let idx = me.bodyRenderer.visibleRowIndices[i];
						return me.datamanager.getData(idx).posting_date;
					});
					let type = column.column.fieldname == "age" ? "mean" : null;
					return frappe.utils.report_column_total(values, column, type);
				}
			}
		});
	}
}
