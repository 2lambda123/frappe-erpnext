# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.utils import cstr, flt
from frappe import _
from erpnext.stock.get_item_details import get_item_details
from frappe.model.document import Document

class PackedItem(Document):
	pass

def validate_uom_for_packed_items(self, packed_items):
	for item in self.items:
		if packed_items[item.item_code]['valid']:
			item.weight_per_unit = flt(packed_items[item.item_code]['weight'])
			item.total_weight = flt(item.weight_per_unit) * flt(item.qty)
		elif not packed_items[item.item_code]['valid']:
			frappe.msgprint(msg = _("Could not calculate weight for {0} as it's items have different UoMs").format(item.item_code), alert=True, indicator='red')
	from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals
	calculate_taxes_and_totals(self)

def get_product_bundle_items(item_code):
	return frappe.db.sql("""select t1.item_code, t1.qty, t1.uom, t1.description
		from `tabProduct Bundle Item` t1, `tabProduct Bundle` t2
		where t2.new_item_code=%s and t1.parent = t2.name order by t1.idx""", item_code, as_dict=1)

def get_packing_item_details(item, company):
	return frappe.db.get_all("Item",
		fields = [
			'item_name',
			'is_stock_item',
			'description',
			'stock_uom',
			'weight_per_unit',
			"`tabItem Default`.default_warehouse"
		],
		filters = {"name": item, "company": company})[0] or {}

def get_bin_qty(item, warehouse):
	det = frappe.db.sql("""select actual_qty, projected_qty from `tabBin`
		where item_code = %s and warehouse = %s""", (item, warehouse), as_dict = 1)
	return det and det[0] or frappe._dict()

def update_packing_list_item(doc, packing_item_code, qty, main_item_row, description):
	if doc.amended_from:
		old_packed_items_map = get_old_packed_item_details(doc.packed_items)
	else:
		old_packed_items_map = False
	item = get_packing_item_details(packing_item_code, doc.company)

	# check if exists
	exists = 0
	for d in doc.get("packed_items"):
		if d.parent_item == main_item_row.item_code and d.item_code == packing_item_code and\
				d.parent_detail_docname == main_item_row.name:
			pi, exists = d, 1
			break

	if not exists:
		pi = doc.append('packed_items', {})

	pi.parent_item = main_item_row.item_code
	pi.item_code = packing_item_code
	pi.item_name = item.item_name
	pi.parent_detail_docname = main_item_row.name
	pi.uom = item.stock_uom
	pi.qty = flt(qty)
	pi.weight_per_unit = item.weight_per_unit
	pi.conversion_factor = main_item_row.conversion_factor
	if description and not pi.description:
		pi.description = description
	if not pi.warehouse and not doc.amended_from:
		pi.warehouse = (main_item_row.warehouse if ((doc.get('is_pos') or item.is_stock_item \
			or not item.default_warehouse) and main_item_row.warehouse) else item.default_warehouse)
	if not pi.batch_no and not doc.amended_from:
		pi.batch_no = cstr(main_item_row.get("batch_no"))
	if not pi.target_warehouse:
		pi.target_warehouse = main_item_row.get("target_warehouse")
	bin = get_bin_qty(packing_item_code, pi.warehouse)
	pi.actual_qty = flt(bin.get("actual_qty"))
	pi.projected_qty = flt(bin.get("projected_qty"))
	if old_packed_items_map and old_packed_items_map.get((packing_item_code, main_item_row.item_code)):
		pi.batch_no = old_packed_items_map.get((packing_item_code, main_item_row.item_code))[0].batch_no
		pi.serial_no = old_packed_items_map.get((packing_item_code, main_item_row.item_code))[0].serial_no
		pi.warehouse = old_packed_items_map.get((packing_item_code, main_item_row.item_code))[0].warehouse

def make_packing_list(doc):
	"""make packing list for Product Bundle item"""
	if doc.get("_action") and doc._action == "update_after_submit": return

	parent_items = []
	for d in doc.get("items"):
		if frappe.db.get_value("Product Bundle", {"new_item_code": d.item_code}):
			for i in get_product_bundle_items(d.item_code):
				update_packing_list_item(doc, i.item_code, flt(i.qty)*flt(d.stock_qty), d, i.description)

			if [d.item_code, d.name] not in parent_items:
				parent_items.append([d.item_code, d.name])

	cleanup_packing_list(doc, parent_items)


def cleanup_packing_list(doc, parent_items):
	"""Remove all those child items which are no longer present in main item table"""
	delete_list = []
	for d in doc.get("packed_items"):
		if [d.parent_item, d.parent_detail_docname] not in parent_items:
			# mark for deletion from doclist
			delete_list.append(d)

	if not delete_list:
		return doc

	packed_items = doc.get("packed_items")
	doc.set("packed_items", [])
	for d in packed_items:
		if d not in delete_list:
			doc.append("packed_items", d)

@frappe.whitelist()
def get_items_from_product_bundle(args):
	args = json.loads(args)
	items = []
	bundled_items = get_product_bundle_items(args["item_code"])
	for item in bundled_items:
		args.update({
			"item_code": item.item_code,
			"qty": flt(args["quantity"]) * flt(item.qty)
		})
		items.append(get_item_details(args))

	return items

def on_doctype_update():
	frappe.db.add_index("Packed Item", ["item_code", "warehouse"])

def get_old_packed_item_details(old_packed_items):
	old_packed_items_map = {}
	for items in old_packed_items:
		old_packed_items_map.setdefault((items.item_code ,items.parent_item), []).append(items.as_dict())
	return old_packed_items_map

def calculate_item_net_weight_from_packed_items(item_details, packed_items):
	qty_details = {}
	for detail in item_details:
		qty_details[detail.item_code] = flt(detail.qty)

	items = {}
	for item in packed_items:
		if item.parent_item in items:
			if not items[item.parent_item]['valid']:
				continue

			if item.uom == items[item.parent_item]['uom']:
				qty = item.qty/qty_details[item.parent_item]
				items[item.parent_item]['weight'] += flt((item.weight_per_unit or 0) * qty)

			else:
				items[item.parent_item]['weight'] = 0
				items[item.parent_item]['valid'] = 0

		else:
			qty = item.qty/qty_details[item.parent_item]
			items[item.parent_item] = {
				'uom': item.uom,
				'weight': flt((item.weight_per_unit or 0) * qty),
				'valid': 1
			}
	return items


