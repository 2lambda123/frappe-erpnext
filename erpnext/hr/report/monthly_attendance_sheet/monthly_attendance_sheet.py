# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _, scrub
from frappe.utils import cstr, cint, getdate, get_last_day, add_months, today, formatdate
from calendar import monthrange
import datetime

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)

	attendance_map = get_attendance_map(conditions, filters)
	employee_map = get_employee_details(filters)
	holiday_map = get_holiday_map(employee_map, filters.default_holiday_list,
		from_date=filters.from_date, to_date=filters.to_date)

	no_of_late_days_as_lwp = cint(frappe.get_cached_value("HR Settings", None, "no_of_late_days"))

	leave_types = frappe.db.sql("select name, is_lwp, include_holiday from `tabLeave Type` order by idx, creation",
		as_dict=1)
	leave_type_map = {}
	for d in leave_types:
		leave_type_map[d.name] = d

	data = []
	for employee in sorted(attendance_map):
		employee_details = employee_map.get(employee)
		if not employee_details:
			continue

		row = frappe._dict({
			'employee': employee,
			'employee_name': employee_details.employee_name,
			'department': employee_details.department,
			'designation': employee_details.designation,
			'from_date': filters.from_date,
			'to_date': filters.to_date,
		})

		row['total_present'] = 0
		row['total_absent'] = 0
		row['total_leave'] = 0
		row['total_half_day'] = 0
		row['total_half_day'] = 0
		row['total_late_entry'] = 0
		row['total_early_exit'] = 0
		row['total_lwp'] = 0
		row['total_deduction'] = 0

		for day in range(filters["total_days_in_month"]):
			attendance_details = attendance_map.get(employee).get(day + 1, frappe._dict())
			attendance_date = datetime.date(year=filters.year, month=filters.month, day=day+1)

			attendance_status = attendance_details.get('status')
			is_holiday = is_date_holiday(attendance_date, holiday_map, employee_details, filters.default_holiday_list)
			if not attendance_status and is_holiday:
				attendance_status = "Holiday"

			day_fieldname = "day_{0}".format(day + 1)
			row["status_" + day_fieldname] = attendance_status
			row["attendance_" + day_fieldname] = attendance_details.name

			attendance_status_abbr = get_attendance_status_abbr(attendance_status, attendance_details.late_entry,
				attendance_details.early_exit, attendance_details.leave_type)
			row[day_fieldname] = attendance_status_abbr

			if attendance_status == "Present":
				row['total_present'] += 1

				if attendance_details.late_entry:
					row['total_late_entry'] += 1
				if attendance_details.early_exit:
					row['total_early_exit'] += 1
			elif attendance_status == "Absent":
				row['total_absent'] += 1
				row['total_deduction'] += 1
			elif attendance_status == "Half Day":
				row['total_half_day'] += 1
				if not attendance_details.leave_type:
					row['total_deduction'] += 0.5
			elif attendance_status == "On Leave":
				leave_details = leave_type_map.get(attendance_details.leave_type, frappe._dict())
				if not is_holiday or leave_details.include_holidays:
					row['total_leave'] += 1

			if attendance_status in ("On Leave", "Half Day") and attendance_details.leave_type:
				leave_details = leave_type_map.get(attendance_details.leave_type, frappe._dict())
				leave_details.has_entry = True

				leave_fieldname = "leave_{0}".format(scrub(leave_details.name))
				leave_count = 0.5 if attendance_status == "Half Day" else 1

				if not is_holiday or leave_details.include_holidays:
					row.setdefault(leave_fieldname, 0)
					row[leave_fieldname] += leave_count

					if leave_details.is_lwp:
						row['total_deduction'] += leave_count
						row['total_lwp'] += leave_count

		row['total_late_deduction'] = 0
		if no_of_late_days_as_lwp:
			row['total_late_deduction'] = row['total_late_entry'] // no_of_late_days_as_lwp
			row['total_deduction'] += row['total_late_deduction']

		data.append(row)

	if data:
		days_row = frappe._dict({})
		for day in range(filters["total_days_in_month"]):
			attendance_date = datetime.date(year=filters.year, month=filters.month, day=day+1)
			day_fieldname = "day_{0}".format(day + 1)
			day_of_the_week = formatdate(attendance_date, "EE")
			days_row[day_fieldname] = day_of_the_week

		data.insert(0, days_row)

	columns = get_columns(filters, leave_types)
	return columns, data


def get_columns(filters, leave_types):
	columns = [
		{"fieldname": "employee", "label": _("Employee"), "fieldtype": "Link", "options": "Employee", "width": 80},
		{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 140},
		{"fieldname": "designation", "label": _("Designation"), "fieldtype": "Link", "options": "Designation", "width": 100},
	]

	for day in range(filters["total_days_in_month"]):
		columns.append({"fieldname": "day_{0}".format(day+1), "label": day+1, "fieldtype": "Data", "width": 40,
			"day": cint(day+1)})

	columns += [
		{"fieldname": "total_present", "label": _("Present"), "fieldtype": "Float", "width": 70, "precision": 1},
		{"fieldname": "total_absent", "label": _("Absent"), "fieldtype": "Float", "width": 70, "precision": 1},
		{"fieldname": "total_half_day", "label": _("Half Day"), "fieldtype": "Float", "width": 75, "precision": 1},
		{"fieldname": "total_leave", "label": _("On Leave"), "fieldtype": "Float", "width": 75, "precision": 1},
		{"fieldname": "total_late_entry", "label": _("Late Entry"), "fieldtype": "Float", "width": 80, "precision": 1},
		{"fieldname": "total_early_exit", "label": _("Early Exit"), "fieldtype": "Float", "width": 75, "precision": 1},
	]

	if cint(frappe.get_cached_value("HR Settings", None, "no_of_late_days")):
		columns.append({"fieldname": "total_late_deduction", "label": _("Late Deduction"), "fieldtype": "Float", "width": 110, "precision": 1})

	columns.append({"fieldname": "total_deduction", "label": _("Total Deduction"), "fieldtype": "Float", "width": 112, "precision": 1})

	for leave_type in leave_types:
		if leave_type.has_entry:
			leave_fieldname = "leave_{0}".format(scrub(leave_type.name))
			columns.append({"fieldname": leave_fieldname, "label": leave_type.name, "fieldtype": "Float", "precision": 1,
				"leave_type": leave_type.name, "is_lwp": cint(leave_type.is_lwp)})

	return columns


def get_attendance_map(conditions, filters):
	attendance_list = frappe.db.sql("""
		select name, employee, day(attendance_date) as day_of_month, attendance_date,
			status, late_entry, early_exit, leave_type
		from tabAttendance
		where docstatus = 1 %s
		order by employee, attendance_date
	""" % conditions, filters, as_dict=1)

	attendance_map = {}
	for d in attendance_list:
		attendance_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, frappe._dict())
		attendance_map[d.employee][d.day_of_month] = d

	return attendance_map


def get_conditions(filters):
	filters = frappe._dict(filters)

	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	if not filters.company:
		frappe.throw(_("Please select Company"))

	filters["year"] = cint(filters["year"])
	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(filters.year, filters.month)[1]
	filters["from_date"] = datetime.date(year=filters.year, month=filters.month, day=1)
	filters["to_date"] = get_last_day(filters["from_date"])

	filters["default_holiday_list"] = frappe.get_cached_value('Company', filters.company, "default_holiday_list")

	conditions = " and month(attendance_date) = %(month)s and year(attendance_date) = %(year)s"

	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters


def get_employee_details(filters):
	employee_map = frappe._dict()

	employee_condition = ""
	if filters.employee:
		employee_condition = " and name = %(employee)s"

	employees = frappe.db.sql("""
		select name, employee_name, designation, department, branch, company, holiday_list
		from tabEmployee
		where company = %(company)s {0}
	""".format(employee_condition), filters, as_dict=1)

	for d in employees:
		employee_map.setdefault(d.name, d)

	return employee_map


def is_date_holiday(attendance_date, holiday_map, employee_details, default_holiday_list):
	if holiday_map:
		emp_holiday_list = get_employee_holiday_list(employee_details, default_holiday_list)
		if emp_holiday_list in holiday_map and getdate(attendance_date) in holiday_map[emp_holiday_list]:
			return True

	return False


def get_employee_holiday_list(employee_details, default_holiday_list):
	return employee_details.holiday_list if employee_details.holiday_list else default_holiday_list


def get_holiday_map(employee_map, default_holiday_list, from_date=None, to_date=None):
	holiday_lists = [employee_map[d]["holiday_list"] for d in employee_map if employee_map[d]["holiday_list"]]
	holiday_lists.append(default_holiday_list)
	holiday_lists = list(set(holiday_lists))
	holiday_map = get_holiday_map_from_holiday_lists(holiday_lists, from_date=from_date, to_date=to_date)
	return holiday_map


def get_holiday_map_from_holiday_lists(holiday_lists, from_date=None, to_date=None):
	holiday_map = frappe._dict()

	date_condition = ""
	if from_date:
		date_condition += " and holiday_date >= %(from_date)s"
	if to_date:
		date_condition += " and holiday_date <= %(to_date)s"

	for holiday_list in holiday_lists:
		if holiday_list:
			args = {'holiday_list': holiday_list, 'from_date': from_date, 'to_date': to_date}
			holidays = frappe.db.sql_list("""
				select holiday_date
				from `tabHoliday`
				where parent=%(holiday_list)s {0}
				order by holiday_date
			""".format(date_condition), args)

			holiday_map.setdefault(holiday_list, holidays)

	return holiday_map


@frappe.whitelist()
def get_attendance_years():
	year_list = frappe.db.sql_list("""
		select distinct YEAR(attendance_date)
		from tabAttendance
		where docstatus = 1
	""")

	if not year_list:
		year_list = []

	year_list.append(getdate().year)
	year_list.append(getdate(add_months(today(), -1)).year)

	year_list = list(set(year_list))
	year_list = sorted(year_list, reverse=True)

	return "\n".join(str(year) for year in year_list)


def get_attendance_status_abbr(attendance_status, late_entry=0, early_exit=0, leave_type=None):
	status_map = {"Present": "P", "Absent": "A", "Half Day": "HD", "On Leave": "L", "Holiday": "H"}

	abbr = status_map.get(attendance_status, '')

	leave_type_abbr = ""
	if leave_type:
		leave_type_abbr = frappe.get_cached_value("Leave Type", leave_type, "abbr")
	if not leave_type_abbr:
		leave_type_abbr = status_map['On Leave']

	if attendance_status == "On Leave":
		abbr = leave_type_abbr

	# if attendance_status == "Half Day" and leave_type:
	# 	abbr = "{0}({1})".format(abbr, leave_type_abbr)

	if cint(late_entry):
		abbr = ">{0}".format(abbr)
	if cint(early_exit):
		abbr = "{0}<".format(abbr)

	return abbr
