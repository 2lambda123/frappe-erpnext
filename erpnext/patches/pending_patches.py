def execute():
	import webnotes
	from webnotes.model.code import get_obj
	from webnotes.modules.module_manager import reload_doc
	sql = webnotes.conn.sql

	reload_doc('hr', 'doctype', 'appraisal')
	reload_doc('hr', 'doctype', 'appraisal_detail')

	sql("update `tabDocField` set `hidden` = 0 where fieldname = 'group_or_ledger' and parent = 'Cost Center'")
	sql("update tabDocPerm set amend = 0 where parent = 'Salary Structure'")
	sql("update tabDocPerm set cancel = 1 where parent = 'Company' and role = 'System Manager'")
	
	if sql("select count(name) from `tabDocField` where label = 'View Ledger Entry' and parent = 'Journal Voucher' and fieldtype = 'Button'")[0][0] > 1:
		sql("delete from `tabDocField` where label = 'View Ledger Entry' and parent = 'Journal Voucher' and fieldtype = 'Button' limit 1")
	if sql("select count(name) from `tabDocField` where label = 'Get Balance' and parent = 'Journal Voucher' and fieldtype = 'Button'")[0][0] > 1:
		sql("delete from `tabDocField` where label = 'Get Balance' and parent = 'Journal Voucher' and fieldtype = 'Button' limit 1")
	
	reload_doc('accounts', 'doctype', 'internal_reconciliation')
	reload_doc('accounts', 'doctype', 'ir_payment_detail')
	reload_doc('accounts', 'Module Def', 'Accounts')
		

		
	if sql("select count(name) from `tabDocField` where label = 'Get Specification Details' and parent = 'QA Inspection Report' and fieldtype = 'Button'")[0][0] > 1:
		sql("delete from `tabDocField` where label = 'Get Specification Details' and parent = 'QA Inspection Report' and fieldtype = 'Button' limit 1")
	
	reload_doc('stock', 'DocType Mapper', 'Purchase Order-Purchase Receipt')
		
	reload_doc('accounts', 'doctype', 'cost_center')
	reload_doc('stock', 'Module Def', 'Stock')
	sql("delete from `tabModule Def Item` where display_name = 'Serial No' and parent = 'Support'")
	sql("update `tabDocType` set subject = 'Item Code: %(item_code)s, Warehouse: %(warehouse)s' where name = 'Serial No'")

	# Patch for adding packing related columns (packed by, checked by, shipping mark etc)
	reload_doc('stock','doctype','delivery_note')
	sql("update `tabDocField` set allow_on_submit = 1 where fieldname = 'page_break'")
	sql("update `tabDocField` set allow_on_submit = 1 where fieldname in ('indent_details', 'po_details', 'purchase_receipt_details', 'entries', 'sales_order_details', 'delivery_note_details', 'quotation_details') and fieldtype = 'Table'")
		
	from webnotes.session_cache import clear_cache
	clear_cache(webnotes.session['user'])

	# FEATURES SETUP
	#----------------
	reload_doc('setup', 'doctype','features_setup')
	flds = ['page_break', 'projects', 'packing_details', 'discounts', 'brands', 'item_batch_nos', 'after_sales_installations', 'item_searial_nos', 'item_group_in_details', 'exports', 'imports', 'item_advanced', 'sales_extras', 'more_info', 'quality', 'manufacturing', 'pos', 'item_serial_nos']
	st = "'"+"', '".join(flds)+"'"
	sql("delete from `tabSingles` where field in (%s) and doctype = 'Features Setup'" % st)
	sql("delete from `tabDocField` where fieldname in (%s) and parent = 'Features Setup'" % st)
	sql("delete from `tabDefaultValue` where defkey in (%s) and parent = 'Control Panel'" % st)

	if not sql("select * from `tabDefaultValue` where defkey like 'fs_%' and parent = 'Control Panel'"):
		rs = sql("select fieldname from tabDocField where parent='Features Setup' and fieldname is not null")
		fs = get_obj('Features Setup', 'Features Setup')
		for d in rs:
			fs.doc.fields[d[0]] = 1
		fs.doc.save()
		fs.validate()
