def execute():
	import webnotes
	from webnotes.modules.module_manager import reload_doc
	from webnotes.model.doc import addchild
	from webnotes.model.code import get_obj
	reload_doc('stock', 'Print Format', 'Delivery Note Packing List Wise')
	reload_doc('stock', 'Print Format', 'Purchase Receipt Format')
	reload_doc('accounts', 'Print Format', 'Payment Receipt Voucher')
	reload_doc('accounts', 'Print Format', 'POS Invoice')
	reload_doc('accounts', 'Print Format', 'Form 16A Print Format')
	reload_doc('accounts', 'Print Format', 'Cheque Printing Format')
	
	if not webnotes.conn.sql("select format from `tabDocFormat` where name = 'POS Invoice' and parent = 'Receivable Voucher'"):		
		dt_obj = get_obj('DocType', 'Receivable Voucher', with_children = 1)
		ch = addchild(dt_obj.doc, 'formats', 'DocFormat', 1)
		ch.format = 'POS Invoice'
		ch.save(1)
