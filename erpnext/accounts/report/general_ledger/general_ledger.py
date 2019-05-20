# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import erpnext
from erpnext import get_company_currency, get_default_company
from erpnext.accounts.report.utils import get_currency, convert_to_presentation_currency
from frappe.utils import getdate, cstr, flt, cint
from frappe import _, _dict
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.report.financial_statements import get_cost_centers_with_children
from frappe.desk.query_report import group_report_data

def execute(filters=None):
	if not filters:
		return [], []

	account_details = {}

	if filters and filters.get('print_in_account_currency') and \
		not filters.get('account'):
		frappe.throw(_("Select an account to print in account currency"))

	for acc in frappe.db.sql("""select name, is_group from tabAccount""", as_dict=1):
		account_details.setdefault(acc.name, acc)

	if filters.get('party'):
		parties = cstr(filters.get("party")).strip()
		filters.party = [d.strip() for d in parties.split(',') if d]

	validate_filters(filters, account_details)

	validate_party(filters)

	filters = set_account_currency(filters)

	columns = get_columns(filters)

	res = get_result(filters, account_details)

	return columns, res


def validate_filters(filters, account_details):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))

	if filters.get("account") and not account_details.get(filters.account):
		frappe.throw(_("Account {0} does not exists").format(filters.account))

	if (filters.get("account") and filters.get("group_by") == _('Group by Account')
		and account_details[filters.account].is_group == 0):
		frappe.throw(_("Can not filter based on Account, if grouped by Account"))

	if filters.get("voucher_no"):
		filters.show_detailed_entries = True

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))

	if filters.get('project'):
		projects = cstr(filters.get("project")).strip()
		filters.project = [d.strip() for d in projects.split(',') if d]

	if filters.get('cost_center'):
		cost_centers = cstr(filters.get("cost_center")).strip()
		filters.cost_center = [d.strip() for d in cost_centers.split(',') if d]


def validate_party(filters):
	party_type, party = filters.get("party_type"), filters.get("party")

	if party:
		if not party_type:
			frappe.throw(_("To filter based on Party, select Party Type first"))
		else:
			for d in party:
				if not frappe.db.exists(party_type, d):
					frappe.throw(_("Invalid {0}: {1}").format(party_type, d))

def set_account_currency(filters):
	filters["company_currency"] = frappe.get_cached_value('Company',  filters.company,  "default_currency")
	if filters.get("account") or (filters.get('party') and len(filters.party) == 1):
		account_currency = None

		if filters.get("account"):
			account_currency = get_account_currency(filters.account)
		elif filters.get("party"):
			gle_currency = frappe.db.get_value(
				"GL Entry", {
					"party_type": filters.party_type, "party": filters.party[0], "company": filters.company
				},
				"account_currency"
			)

			if gle_currency:
				account_currency = gle_currency
			else:
				account_currency = (None if not frappe.get_meta(filters.party_type).has_field('default_currency') else
					frappe.db.get_value(filters.party_type, filters.party[0], "default_currency"))

		filters["account_currency"] = account_currency or filters.company_currency
		if filters.account_currency != filters.company_currency and not filters.presentation_currency:
			filters.presentation_currency = filters.account_currency

	return filters

def get_result(filters, account_details):
	gl_entries = get_gl_entries(filters)

	group_field = group_by_field(filters.get('group_by'))
	group_by = [None]
	if group_field:
		group_by.append(group_field)

	result = group_report_data(gl_entries, group_by,
		calculate_totals=lambda rows, grouped_by: calculate_opening_closing(filters, rows, grouped_by),
		postprocess_group=lambda group_object, grouped_by: postprocess_group(filters, group_object, grouped_by)
	)

	return result

def get_gl_entries(filters):
	currency_map = get_currency(filters)
	select_fields = """, debit, credit, debit_in_account_currency, credit_in_account_currency,
		reference_no, reference_date, against_voucher"""

	group_by_statement = ''
	order_by_statement = "order by posting_date, account"

	if filters.get("group_by") == _("Group by Voucher"):
		order_by_statement = "order by posting_date, voucher_type, voucher_no"

	if not cint(filters.get("show_detailed_entries")):
		group_by_statement = "group by voucher_type, voucher_no, account, cost_center, party_type, party"
		select_fields = """,
			if(sum(debit-credit) > 0, sum(debit-credit), 0) as debit,
			if(sum(debit-credit) < 0, -sum(debit-credit), 0) as credit,
			if(sum(debit_in_account_currency-credit_in_account_currency) > 0, sum(debit_in_account_currency-credit_in_account_currency), 0) as debit_in_account_currency,
			if(sum(debit_in_account_currency-credit_in_account_currency) < 0, -sum(debit_in_account_currency-credit_in_account_currency), 0) as credit_in_account_currency,
			GROUP_CONCAT(DISTINCT reference_no SEPARATOR ', ') as reference_no,
			min(reference_date) as reference_date,
			GROUP_CONCAT(DISTINCT against_voucher SEPARATOR ', ') as against_voucher"""

	gl_entries = frappe.db.sql(
		"""
		select
			posting_date, account, party_type, party,
			voucher_type, voucher_no, cost_center, project, account_currency,
			remarks, against, is_opening, against_voucher_type {select_fields}
		from `tabGL Entry`
		where company=%(company)s {conditions} {group_by_statement}
		{order_by_statement}
		""".format(
			select_fields=select_fields, conditions=get_conditions(filters),
			group_by_statement=group_by_statement,
			order_by_statement=order_by_statement
		),
		filters, as_dict=1)

	if filters.get('presentation_currency'):
		return convert_to_presentation_currency(gl_entries, currency_map)
	else:
		return gl_entries


def get_conditions(filters):
	conditions = []
	if filters.get("account"):
		lft, rgt = frappe.db.get_value("Account", filters["account"], ["lft", "rgt"])
		conditions.append("""account in (select name from tabAccount
			where lft>=%s and rgt<=%s and docstatus<2)""" % (lft, rgt))

	if filters.get("cost_center"):
		filters.cost_center = get_cost_centers_with_children(filters.cost_center)
		conditions.append("cost_center in %(cost_center)s")

	if filters.get("voucher_no"):
		voucher_filter_method = filters.get("voucher_filter_method")
		if voucher_filter_method == "Posted Against Voucher":
			conditions.append("against_voucher=%(voucher_no)s")
		elif voucher_filter_method == "Posted By and Against Voucher":
			conditions.append("voucher_no=%(voucher_no)s or against_voucher=%(voucher_no)s")
		else:
			conditions.append("voucher_no=%(voucher_no)s")

	if filters.get("against_voucher"):
		conditions.append("against_voucher=%(against_voucher)s")

	if filters.get("reference_no"):
		conditions.append("reference_no=%(reference_no)s")

	if filters.get("group_by") == "Group by Party" and not filters.get("party_type"):
		conditions.append("party_type in ('Customer', 'Supplier')")

	if filters.get("party_type"):
		conditions.append("party_type=%(party_type)s")

	if filters.get("party"):
		conditions.append("party in %(party)s")

	if not (filters.get("account") or filters.get("party") or
		filters.get("group_by") in ["Group by Account", "Group by Party"]):
		conditions.append("posting_date >=%(from_date)s")

	conditions.append("posting_date <=%(to_date)s")

	if filters.get("project"):
		conditions.append("project in %(project)s")

	if filters.get("sales_person"):
		lft, rgt = frappe.db.get_value("Sales Person", filters.get("sales_person"), ["lft", "rgt"])
		conditions.append("""exists(select name from `tabSales Team` steam where
			steam.sales_person in (select name from `tabSales Person` where lft >= {0} and rgt <= {1})
			and steam.parent = party and steam.parenttype = party_type)""".format(lft, rgt))

	if filters.get("finance_book"):
		conditions.append("ifnull(finance_book, '') in (%(finance_book)s, '')")

	from frappe.desk.reportview import build_match_conditions
	match_conditions = build_match_conditions("GL Entry")

	if match_conditions:
		conditions.append(match_conditions)

	return "and {}".format(" and ".join(conditions)) if conditions else ""


def calculate_opening_closing(filters, gl_entries, grouped_by):
	totals = get_totals_dict()

	def update_totals_for(key, gle):
		totals[key].debit += flt(gle.debit)
		totals[key].credit += flt(gle.credit)

		totals[key].debit_in_account_currency += flt(gle.debit_in_account_currency)
		totals[key].credit_in_account_currency += flt(gle.credit_in_account_currency)

	from_date, to_date = getdate(filters.from_date), getdate(filters.to_date)
	for gle in gl_entries:
		if gle.posting_date < from_date or cstr(gle.is_opening) == "Yes":
			update_totals_for('opening', gle)
			update_totals_for('closing', gle)
			gle.to_remove = True
		elif gle.posting_date <= to_date:
			update_totals_for('total', gle)
			update_totals_for('closing', gle)

	return totals

def postprocess_group(filters, group_object, grouped_by):
	group_object.rows = filter(lambda d: not d.get("to_remove"), group_object.rows)

	group = grouped_by[-1]
	if group_object.rows:
		if group.fieldname == "party":
			if group_object.rows[0].party_type == "Customer":
				customer = frappe.get_cached_doc("Customer", group.value)
				group_object.sales_person = ", ".join(set([d.sales_person for d in customer.sales_team]))

		if group.fieldname != 'voucher_no':
			group_object.rows.insert(0, group_object.totals.opening)

		# group_object.rows.append(group_object.totals.total)

		if group.fieldname != 'voucher_no':
			group_object.rows.append(group_object.totals.closing)

		balance, balance_in_account_currency = 0, 0
		inv_details = get_supplier_invoice_details()

		for d in group_object.rows:
			if not d.posting_date:
				balance = 0

			balance = get_balance(d, balance, 'debit', 'credit')
			d['balance'] = balance

			d['account_currency'] = filters.account_currency
			d['currency'] = filters.presentation_currency or filters.company_currency
			d['bill_no'] = inv_details.get(d.get('against_voucher'), '')

	# Do not show totals as they have already been added as rows
	del group_object['totals']

def get_balance(row, balance, debit_field, credit_field):
	balance += (row.get(debit_field, 0) - row.get(credit_field, 0))
	return balance

def get_totals_dict():
	def _get_debit_credit_dict(label):
		return _dict(
			account="'{0}'".format(label),
			debit=0.0,
			credit=0.0,
			debit_in_account_currency=0.0,
			credit_in_account_currency=0.0,
			_isGroupTotal=True
		)
	return _dict(
		opening=_get_debit_credit_dict(_('Opening')),
		total=_get_debit_credit_dict(_('Total')),
		closing=_get_debit_credit_dict(_('Closing (Opening + Total)')),
		_isGroupTotal=True
	)

def group_by_field(group_by):
	if group_by == _('Group by Party'):
		return 'party'
	elif group_by == _('Group by Account'):
		return 'account'
	elif group_by == _('Group by Voucher'):
		return 'voucher_no'
	else:
		return None

def get_supplier_invoice_details():
	inv_details = {}
	for d in frappe.db.sql(""" select name, bill_no from `tabPurchase Invoice`
		where docstatus = 1 and bill_no is not null and bill_no != '' """, as_dict=1):
		inv_details[d.name] = d.bill_no

	return inv_details

def get_columns(filters):
	if filters.get("presentation_currency"):
		currency = filters["presentation_currency"]
	else:
		if filters.get("company"):
			currency = get_company_currency(filters["company"])
		else:
			company = get_default_company()
			currency = get_company_currency(company)

	columns = [
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 80
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"width": 120
		},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 150
		},
		{
			"label": _("Account"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 150
		},
		{
			"label": _("Party Type"),
			"fieldname": "party_type",
			"width": 100
		},
		{
			"label": _("Party"),
			"fieldname": "party",
			"width": 150,
			"fieldtype": "Dynamic Link",
			"options": "party_type"
		},
		{
			"label": _("Debit ({0})".format(currency)),
			"fieldname": "debit",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100
		},
		{
			"label": _("Credit ({0})".format(currency)),
			"fieldname": "credit",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100
		},
		{
			"label": _("Balance ({0})".format(currency)),
			"fieldname": "balance",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"width": 200
		},
		{
			"label": _("Against Account"),
			"fieldname": "against",
			"width": 120
		},
		{
			"label": _("Against Voucher Type"),
			"fieldname": "against_voucher_type",
			"width": 120
		},
		{
			"label": _("Against Voucher"),
			"fieldname": "against_voucher",
			"fieldtype": "Dynamic Link",
			"options": "against_voucher_type",
			"width": 150
		},
		{
			"label": _("Ref Date"),
			"fieldname": "reference_date",
			"fieldtype": "Date",
			"width": 90
		},
		{
			"label": _("Ref No"),
			"fieldname": "reference_no",
			"width": 80
		},
		{
			"label": _("Project"),
			"options": "Project",
			"fieldname": "project",
			"width": 100
		},
		{
			"label": _("Cost Center"),
			"options": "Cost Center",
			"fieldname": "cost_center",
			"width": 100
		},
		{
			"label": _("Supplier Invoice No"),
			"fieldname": "bill_no",
			"fieldtype": "Data",
			"width": 100
		},
	]

	return columns
