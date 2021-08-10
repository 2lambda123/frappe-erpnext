# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
from erpnext.e_commerce.doctype.item_review.item_review import get_item_reviews
from erpnext.e_commerce.doctype.website_item.website_item import check_if_user_is_customer
from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import get_shopping_cart_settings

def get_context(context):
	context.no_cache = 1
	context.full_page = True
	context.reviews = None

	if frappe.form_dict and frappe.form_dict.get("item_code"):
		context.item_code = frappe.form_dict.get("item_code")
		context.web_item = frappe.db.get_value("Website Item", {"item_code": context.item_code}, "name")
		context.user_is_customer = check_if_user_is_customer()
		context.enable_reviews = get_shopping_cart_settings().enable_reviews
		if context.enable_reviews:
			get_item_reviews(context.web_item, 0, 10, context)
