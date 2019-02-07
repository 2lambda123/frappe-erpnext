import frappe, json, os
from frappe.utils import flt
from erpnext.controllers.taxes_and_totals import get_itemised_tax
from frappe import _

def update_itemised_tax_data(doc):
	if not doc.taxes: return

	itemised_tax = get_itemised_tax(doc.taxes)

	for row in doc.items:
		tax_rate = 0.0
		if itemised_tax.get(row.item_code):
			tax_rate = sum([tax.get('tax_rate', 0) for d, tax in itemised_tax.get(row.item_code).items()])

		row.tax_rate = flt(tax_rate, row.precision("tax_rate"))
		row.tax_amount = flt((row.net_amount * tax_rate) / 100, row.precision("net_amount"))
		row.total_amount = flt((row.net_amount + row.tax_amount), row.precision("total_amount"))
	
def get_rate_wise_tax_data(items):
	tax_data = {}
	for rate in set([item.item_tax_rate for item in items]):
		for key, value in json.loads(rate).items():
			tax_data.setdefault(key, {
				"tax_rate": value,
				"taxable_amount": sum([item.net_amount for item in items if item.item_tax_rate == rate]),
				"tax_amount": sum([item.tax_amount for item in items if item.item_tax_rate == rate]),
				"tax_exemption_reason": frappe.db.get_value("Account", key, "tax_exemption_reason")
			})
	return tax_data

@frappe.whitelist()
def export_invoices(filters=None):
	saved_xmls = []
	invoices = frappe.get_all("Sales Invoice", filters=get_conditions(filters), fields=["*"])
	for invoice in invoices:
		invoice = prepare_invoice(invoice)
		invoice_xml = frappe.render_template('erpnext/regional/italy/e-invoice.xml', context={"doc": invoice}, is_path=True)
		company_tax_id = invoice.company_data.tax_id if invoice.company_data.tax_id.startswith("IT") else "IT" + invoice.company_data.tax_id
		xml_filename = "{company_tax_id}_{invoice_number}.xml".format(
			company_tax_id=company_tax_id,
			invoice_number=extract_doc_number(invoice)
		)
		xml_filename = frappe.get_site_path("private", "files", xml_filename)
		
		with open(xml_filename, "wb") as xml_file:
			xml_file.write(invoice_xml)
			saved_xmls.append(xml_filename)

	zip_filename = "e-invoices_{0}.zip".format(frappe.generate_hash(length=6))

	download_zip(saved_xmls, zip_filename)

	cleanup_files(saved_xmls)

@frappe.whitelist()
def prepare_invoice(invoice):
	#set company information
	company = frappe.get_doc("Company", invoice.company)
	#company_fiscal_code, fiscal_regime, company_tax_id = frappe.db.get_value("Company", invoice.company, ["fiscal_code", "fiscal_regime", "tax_id"])

	invoice["progressive_number"] = extract_doc_number(invoice)
	invoice["company_data"] = company
	invoice["company_address_data"] = frappe.get_doc("Address", invoice.company_address)
	invoice["company_contact_data"] = frappe.db.get_value("Company", filters=invoice.company, fieldname=["phone_no", "email"], as_dict=1)

	#Set invoice type
	if invoice.is_return and invoice.return_against:
		invoice["type_of_document"] = "TD04" #Credit Note (Nota di Credito)
		invoice["return_against_corrected"] =  extract_doc_number(frappe.get_doc("Sales Invoice", invoice.return_against))
	else:
		invoice["type_of_document"] = "TD01" #Sales Invoice (Fattura)

	#set customer information
	invoice["customer_data"] = frappe.get_doc("Customer", invoice.customer)
	invoice["customer_address_data"] = frappe.get_doc("Address", invoice.customer_address)

	if invoice.shipping_address_name:
		invoice["shipping_address_data"] = frappe.get_doc("Address", invoice.shipping_address_name)


	if invoice["customer_data"].is_public_administration:
		invoice["transmission_format_code"] = "FPA12"
	else:
		invoice["transmission_format_code"] = "FPR12"


	items = frappe.get_all("Sales Invoice Item", filters={"parent":invoice.name}, fields=["*"], order_by="idx")
	taxes = frappe.get_all("Sales Taxes and Charges", filters={"parent":invoice.name}, fields=["*"], order_by="idx")
	tax_data = get_invoice_summary(items, taxes) #get_rate_wise_tax_data(invoice["invoice_items"])

	invoice["tax_data"] = tax_data

	#Check if stamp duty (Bollo) of 2 EUR exists.
	stamp_duty_charge_row = next((tax for tax in taxes if tax.charge_type == _("Actual") and tax.tax_amount == 2.0 ), None)
	if stamp_duty_charge_row:
		invoice["stamp_duty"] = stamp_duty_charge_row.tax_amount

	#append items, and tax exemption reason.
	for item in items:
		if item.tax_rate == 0.0:
			item["tax_exemption_reason"] = tax_data["0.0"]["tax_exemption_reason"]

	invoice["invoice_items"] = items

	invoice["payment_terms"] = frappe.get_all("Payment Schedule", filters={"parent": invoice.name}, fields=["*"])

	return invoice

def get_conditions(filters):
	filters = json.loads(filters)

	conditions = {"docstatus": 1}

	if filters.get("company"): conditions["company"] = filters["company"]
	if filters.get("customer"): conditions["customer"] =  filters["customer"]

	if filters.get("from_date"): conditions["posting_date"] = (">=", filters["from_date"])
	if filters.get("to_date"): conditions["posting_date"] = ("<=", filters["to_date"])

	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ("between", [filters.get("from_date"), filters.get("to_date")])

	return conditions

#TODO: Use function from frappe once PR #6853 is merged.
def download_zip(files, output_filename):
	from zipfile import ZipFile

	input_files = [filename for filename in files]
	output_path = frappe.get_site_path('private', 'files', output_filename)

	with ZipFile(output_path, 'w') as output_zip:
		for input_file in input_files:
			output_zip.write(input_file, arcname=os.path.basename(input_file))

	with open(output_path, 'rb') as fileobj:
		filedata = fileobj.read()

	frappe.local.response.filename = output_filename
	frappe.local.response.filecontent = filedata
	frappe.local.response.type = "download"

def cleanup_files(files):
	#TODO: Clean up XML files after ZIP gets downloaded
	pass

def extract_doc_number(doc):
	if not hasattr(doc, "naming_series"):
		return doc.name

	name_parts = doc.name.split("-")

	if hasattr(doc, "amended_from"):
		if doc.amended_from:
			return name_parts[-2:-1][0]
		else:
			return name_parts[-1:][0]
	else:
		return doc.name

def get_invoice_summary(items, taxes):
	summary_data = frappe._dict()
	for tax in taxes:
		#Include only VAT charges.
		if tax.charge_type == "Actual":
			continue

		#Check item tax rates if tax rate is zero.
		if tax.rate == 0:
			for item in items:
				item_tax_rate = json.loads(item.item_tax_rate)
				if tax.account_head in item_tax_rate:
					key = str(item_tax_rate[tax.account_head])
					summary_data.setdefault(key, {"tax_amount": 0.0, "taxable_amount": 0.0, "tax_exemption_reason": "", "tax_exemption_law": ""})
					summary_data[key]["tax_amount"] += item.tax_amount
					summary_data[key]["taxable_amount"] += item.net_amount
					if key == "0.0":
						summary_data[key]["tax_exemption_reason"] = tax.tax_exemption_reason
						summary_data[key]["tax_exemption_law"] = tax.tax_exemption_law

			if summary_data == {}: #Zero VAT has not been set on any item. zero vat from tax row.
				summary_data.setdefault("0.0", {"tax_amount": 0.0, "taxable_amount": tax.total,
					"tax_exemption_reason": tax.tax_exemption_reason, "tax_exemption_law": tax.tax_exemption_law})

		else:
			item_wise_tax_detail = json.loads(tax.item_wise_tax_detail)
			for rate_item in [tax_item for tax_item in item_wise_tax_detail.items() if tax_item[1][0] == tax.rate]:
				key = str(tax.rate)
				if not summary_data.get(key): summary_data.setdefault(key, {"tax_amount": 0.0, "taxable_amount": 0.0})
				summary_data[key]["tax_amount"] += rate_item[1][1]
				summary_data[key]["taxable_amount"] += sum([item.net_amount for item in items if item.item_code == rate_item[0]])

	return summary_data
