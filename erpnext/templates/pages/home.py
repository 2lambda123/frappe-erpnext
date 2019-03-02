# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint

no_cache = 1
no_sitemap = 1

def get_context(context):
	homepage = frappe.get_doc('Homepage')

	for item in homepage.products:
		route = frappe.db.get_value('Item', item.item_code, 'route')
		if route:
			item.route = '/' + route

	homepage.title = homepage.title or homepage.company
	context.title = homepage.title
	context.homepage = homepage

	context.metatags = context.metatags or frappe._dict({})
	context.metatags.image = homepage.hero_image or None
	context.metatags.description = homepage.description or None

	if homepage.slideshow:
		doc = frappe.get_doc('Website Slideshow', homepage.slideshow)
		context.slideshow = homepage.slideshow
		context.slideshow_header = doc.header
		context.slides = doc.slideshow_items

	context.blogs = frappe.get_all('Blog Post',
		fields=['title', 'blogger', 'blog_intro', 'route'],
		filters={
			'published': 1
		},
		order_by='modified desc',
		limit=3
	)

	context.email = frappe.db.get_single_value('Contact Us Settings', 'email_id')
	context.phone = frappe.db.get_single_value('Contact Us Settings', 'phone')
	context.explore_link = '/products'

	homepage_sections = frappe.get_all('Homepage Section', order_by='section_order asc')
	context.homepage_sections = [frappe.get_doc('Homepage Section', name) for name in homepage_sections]

	for section in context.homepage_sections:
		section.column_value = cint(12 / cint(section.no_of_columns or 3))
