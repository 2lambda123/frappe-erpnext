def execute():
	import webnotes
	from webnotes.model.code import get_obj
	
	# select jv where against_jv exists
	jv = webnotes.conn.sql("select distinct parent from `tabJournal Voucher Detail` where docstatus = 1 and ifnull(against_jv, '') != ''")

	for d in jv:
		jv_obj = get_obj('Journal Voucher', d[0], with_children=1)

		# cancel
		get_obj(dt='GL Control').make_gl_entries(jv_obj.doc, jv_obj.doclist, cancel =1, adv_adj = 1)

		#re-submit
		get_obj(dt='GL Control').make_gl_entries(jv_obj.doc, jv_obj.doclist, cancel =0, adv_adj = 1)
