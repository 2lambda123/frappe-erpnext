# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestQualityReview(unittest.TestCase):

	def test_quality_review(self):
		create_procedure()
		create_unit()
		create_goal()
		test_create_review = create_review()
		test_get_review = get_review()
		self.assertEquals(test_create_review.name, test_get_review.name)

def create_review():
	review = frappe.get_doc({
		"doctype": "Quality Review",
		"goal": "_Test Quality Goal",
		"procedure": "_Test Quality Procedure",
		"scope": "Company",
		"date": ""+ frappe.utils.nowdate() +"",
		"values": [
			{
				"objective": "_Test Quality Objective",
				"target": "100",
				"achieved": "100",
				"unit": "_Test UOM"
			}
		]
	})
	review_exist = frappe.get_list("Quality Review", filters={"goal": "_Test Quality Goal"})
	if len(review_exist) == 0:
		review.insert()
		return review
	else:
		return review_exist[0]

def get_review():
	review = frappe.get_list("Quality Review", filters={"goal": "_Test Quality Goal"})
	return review[0]

def create_procedure():
	procedure = frappe.get_doc({
		"doctype": "Quality Procedure",
		"procedure": "_Test Quality Procedure",
		"procedure_step": [
			{
				"step": "_Test Quality Procedure Table",
			}
		]
	})
	procedure_exist = frappe.db.exists("Quality Procedure",""+ procedure.procedure +"")
	if not procedure_exist:
		procedure.insert()

def create_unit():
	unit = frappe.get_doc({
		"doctype": "UOM",
		"uom_name": "_Test UOM",
	})
	unit_exist = frappe.db.exists("UOM", ""+ unit.uom_name +"")
	if not unit_exist:
		unit.insert()

def create_goal():
	goal = frappe.get_doc({
		"doctype": "Quality Goal",
		"goal": "_Test Quality Goal",
		"procedure": "_Test Quality Procedure",
		"revision": "1",
		"frequency": "None",
		"measurable": "Yes",
		"objective": [
			{
				"objective": "_Test Quality Objective 1",
				"target": "100",
				"unit": "_Test UOM"
			}
		]
	})
	goal_exist = frappe.db.exists("Quality Goal", ""+ goal.goal +"")
	if not goal_exist:
		goal.insert()