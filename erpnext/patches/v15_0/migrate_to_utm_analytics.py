import click
import frappe
from frappe.query_builder.functions import Coalesce


def execute():
	"""
	Remove Lead Source doctype and use Marketing Source Instead
	Ensure that for each Campaign, a Marketing Campaign is also set
	"""

	ls = frappe.qb.DocType("Lead Source")
	ms = frappe.qb.DocType("Marketing Source")

	# Fetch all Lead Sources
	lead_sources = frappe.qb.from_(ls).select(ls.source_name, ls.details).run(as_dict=True)

	# Prepare the insert query with IGNORE
	insert_query = frappe.qb.into(ms).ignore().columns(ms.name, ms.description)

	# Add values for each Lead Source
	for source in lead_sources:
		insert_query = insert_query.insert(source.source_name, Coalesce(source.details, ""))

	# Execute the insert query
	insert_query.run()
	frappe.delete_doc("DocType", "Lead Source", ignore_missing=True)

	campaign = frappe.qb.DocType("Campaign")
	marketing_campaign = frappe.qb.DocType("Marketing Campaign")

	# Fetch all Campaigns
	campaigns = (
		frappe.qb.from_(campaign).select(campaign.campaign_name, campaign.description).run(as_dict=True)
	)

	# Prepare the insert query with IGNORE
	insert_query = (
		frappe.qb.into(marketing_campaign)
		.ignore()
		.columns(marketing_campaign.name, marketing_campaign.campaign_description)
	)

	# Add values for each Campaign
	for camp in campaigns:
		insert_query = insert_query.insert(camp.campaign_name, Coalesce(camp.description, ""))

	# Execute the insert query
	insert_query.run()

	click.secho(
		f"Inserted {len(lead_sources)} Lead Sources into Marketing Sources and deleted Lead Source.\n"
		f"Inserted {len(campaigns)} Campaigns into Marketing Campaigns.\n"
		"You can also make use of the new Marketing Medium for analytics, now.",
		fg="green",
	)
