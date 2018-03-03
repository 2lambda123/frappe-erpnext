# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import flt, getdate, get_url
from frappe import _

from frappe.model.document import Document
from erpnext.controllers.queries import get_filters_cond
from frappe.desk.reportview import get_match_cond

class Project(Document):
    def get_feed(self):
        return '{0}: {1}'.format(_(self.status), self.project_name)

    def onload(self):
        """Load project tasks for quick view"""
        if not self.get('__unsaved') and not self.get("tasks"):
            self.load_tasks()

        self.set_onload('activity_summary', frappe.db.sql('''select activity_type,
            sum(hours) as total_hours
            from `tabTimesheet Detail` where project=%s and docstatus < 2 group by activity_type
            order by total_hours desc''', self.name, as_dict=True))


        roles_and_responsibilities = frappe.db.sql("select name1,party,project_role from `tabRoles And Responsibilities` where parent='{0}'".format(self.name))
        
        self.client_steering_name = ''
        self.client_ownership_name = ''
        self.client_management_name = ''
        self.client_technical_name = ''
        self.tawari_steering_name = ''
        self.tawari_ownership_name = ''
        self.tawari_management_name = ''
        self.tawari_technical_name = ''
        self.partner_steering_name = ''
        self.partner_ownership_name = ''
        self.partner_management_name = ''
        self.partner_technical_name = ''
                
        for row in roles_and_responsibilities:
            if row:
                if row[1] == 'Client':
                    if row[2] == 'Steering Committee':
                        self.client_steering_name = row[0]
                    if row[2] == 'Ownership level':
                        self.client_ownership_name = row[0]
                    if row[2] == 'Project Management':
                        self.client_management_name = row[0]
                    if row[2] == 'Technical management':
                        self.client_technical_name = row[0]
                if row[1] == 'Tawari':
                    if row[2] == 'Steering Committee':
                        self.tawari_steering_name = row[0]
                    if row[2] == 'Ownership level':
                        self.tawari_ownership_name = row[0]
                    if row[2] == 'Project Management':
                        self.tawari_management_name = row[0]
                    if row[2] == 'Technical management':
                        self.tawari_technical_name = row[0]
                if row[1] == 'Partner/Supplier':
                    if row[2] == 'Steering Committee':
                        self.partner_steering_name = row[0]
                    if row[2] == 'Ownership level':
                        self.partner_ownership_name = row[0]
                    if row[2] == 'Project Management':
                        self.partner_management_name = row[0]
                    if row[2] == 'Technical management':
                        self.partner_technical_name = row[0]




    def __setup__(self):
        self.onload()


    def after_insert(self):
        self.validate_project_roles()


    def load_tasks(self):
        """Load `tasks` from the database"""
        self.tasks = []
        for task in self.get_tasks():
            self.append("tasks", {
                "title": task.subject,
                "status": task.status,
                "start_date": task.exp_start_date,
                "end_date": task.exp_end_date,
                "description": task.description,
                "task_id": task.name,
                "task_weight": task.task_weight
            })

    def get_tasks(self):
        return frappe.get_all("Task", "*", {"project": self.name}, order_by="exp_start_date asc")

    def validate(self):
        self.validate_dates()
        self.validate_weights()
        self.sync_tasks()
        self.tasks = []
        self.send_welcome_email()
        

    def validate_project_roles(self):
        pass
        #~ if self.project_manager:
            #~ user_emp = frappe.db.sql("select user_id from `tabEmployee` where name = '{0}'".format(self.project_manager))
            #~ # frappe.throw(user_emp[0].user_id)
            #~ user = frappe.get_doc("User", user_emp[0][0])
            #~ user.add_roles("Project Manager")
            #~ frappe.get_doc(dict(
            #~ doctype='User Permission',
            #~ user=user_emp[0][0],
            #~ allow="Project",
            #~ for_value=self.name,
            #~ apply_for_all_roles=apply
            #~ )).insert(ignore_permissions = True)
            #~ # frappe.permissions.add_user_permission("Project", self.name, user_emp[0].user_id)

        # if self.project_budget_controller:
        #   user_emp = frappe.db.sql("select user_id from `tabEmployee` where name = '{0}'".format(self.project_budget_controller))
        #   user = frappe.get_doc("User", user_emp[0][0])
        #   user.add_roles("Project Budget Controller")
        #   frappe.get_doc(dict(
        #   doctype='User Permission',
        #   user=user_emp[0][0],
        #   allow="Project",
        #   for_value=self.name,
        #   apply_for_all_roles=apply
        #   )).insert(ignore_permissions = True)
            # frappe.permissions.add_user_permission("Project", self.name, user_emp[0].user_id)
        #~ pdds = frappe.db.sql("select parent from `tabUserRole` where role = 'Projects Department Director'")
        #~ for pdd in pdds:
            #~ if pdd[0] and pdd[0] != "Administrator":
                #~ frappe.get_doc(dict(
                #~ doctype='User Permission',
                #~ user=pdd[0],
                #~ allow="Project",
                #~ for_value=self.name,
                #~ apply_for_all_roles=apply
                #~ )).insert(ignore_permissions = True)

    def validate_dates(self):
        if self.start_date and self.end_date:
            if getdate(self.end_date) < getdate(self.start_date):
                frappe.throw(_("Expected End Date can not be less than Expected Start Date"))
                
    def validate_weights(self):
        sum = 0
        for task in self.tasks:
            if task.task_weight > 0:
                sum = sum + task.task_weight
        if sum > 0 and sum != 1:
            frappe.throw(_("Total of all task weights should be 1. Please adjust weights of all Project tasks accordingly"))

    def sync_tasks(self):
        """sync tasks and remove table"""
        if self.flags.dont_sync_tasks: return

        task_names = []
        for t in self.tasks:
            if t.task_id:
                task = frappe.get_doc("Task", t.task_id)
            else:
                task = frappe.new_doc("Task")
                task.project = self.name
            task.update({
                "subject": t.title,
                "status": t.status,
                "exp_start_date": t.start_date,
                "exp_end_date": t.end_date,
                "description": t.description,
                "task_weight": t.task_weight
            })

            task.flags.ignore_links = True
            task.flags.from_project = True
            task.flags.ignore_feed = True
            task.save(ignore_permissions = True)
            task_names.append(task.name)

        # delete
        for t in frappe.get_all("Task", ["name"], {"project": self.name, "name": ("not in", task_names)}):
            frappe.delete_doc("Task", t.name)

        self.update_percent_complete()
        self.update_costing()

    def update_project(self):
        self.update_percent_complete()
        self.update_costing()
        self.flags.dont_sync_tasks = True
        self.save(ignore_permissions = True)

    def update_percent_complete(self):
        total = frappe.db.sql("""select count(name) from tabTask where project=%s""", self.name)[0][0]
        if (self.percent_complete_method == "Task Completion" and total > 0) or (not self.percent_complete_method and total > 0):
            completed = frappe.db.sql("""select count(name) from tabTask where
                project=%s and status in ('Closed', 'Cancelled')""", self.name)[0][0]
            self.percent_complete = flt(flt(completed) / total * 100, 2)

        if (self.percent_complete_method == "Task Progress" and total > 0):
            progress = frappe.db.sql("""select sum(progress) from tabTask where
                project=%s""", self.name)[0][0]
            self.percent_complete = flt(flt(progress) / total, 2)

        if (self.percent_complete_method == "Task Weight" and total > 0):
            weight_sum = frappe.db.sql("""select sum(task_weight) from tabTask where
                project=%s""", self.name)[0][0]
            if weight_sum == 1:
                weighted_progress = frappe.db.sql("""select progress,task_weight from tabTask where
                    project=%s""", self.name,as_dict=1)
                pct_complete=0
                for row in weighted_progress:
                    pct_complete += row["progress"] * row["task_weight"]
                self.percent_complete = flt(flt(pct_complete), 2)

    def update_costing(self):
        from_time_sheet = frappe.db.sql("""select
            sum(costing_amount) as costing_amount,
            sum(billing_amount) as billing_amount,
            min(from_time) as start_date,
            max(to_time) as end_date,
            sum(hours) as time
            from `tabTimesheet Detail` where project = %s and docstatus = 1""", self.name, as_dict=1)[0]

        from_expense_claim = frappe.db.sql("""select
            sum(total_sanctioned_amount) as total_sanctioned_amount
            from `tabExpense Claim` where project = %s and approval_status='Approved'
            and docstatus = 1""",
            self.name, as_dict=1)[0]

        self.actual_start_date = from_time_sheet.start_date
        self.actual_end_date = from_time_sheet.end_date

        self.total_costing_amount = from_time_sheet.costing_amount
        self.total_billing_amount = from_time_sheet.billing_amount
        self.actual_time = from_time_sheet.time

        self.total_expense_claim = from_expense_claim.total_sanctioned_amount

        self.gross_margin = flt(self.total_billing_amount) - flt(self.total_costing_amount)

        if self.total_billing_amount:
            self.per_gross_margin = (self.gross_margin / flt(self.total_billing_amount)) *100

    def update_purchase_costing(self):
        total_purchase_cost = frappe.db.sql("""select sum(base_net_amount)
            from `tabPurchase Invoice Item` where project = %s and docstatus=1""", self.name)

        self.total_purchase_cost = total_purchase_cost and total_purchase_cost[0][0] or 0

    def send_welcome_email(self):
        url = get_url("/project/?name={0}".format(self.name))
        messages = (
        _("You have been invited to collaborate on the project: {0}".format(self.name)),
        url,
        _("Join")
        )

        content = """
        <p>{0}.</p>
        <p><a href="{1}">{2}</a></p>
        """

        for user in self.users:
            if user.welcome_email_sent==0:
                frappe.sendmail(user.user, subject=_("Project Collaboration Invitation"), content=content.format(*messages))
                user.welcome_email_sent=1

    def on_update(self):
        self.load_tasks()
        self.sync_tasks()


    def existing_project_charter(self):
        project_name = frappe.db.sql("select name from `tabProject Charter` where project='{0}'".format(self.name))
        if project_name:
            return project_name[0][0]

            # doc_a = frappe.get_doc("Project",self.name)
            # doc_b = frappe.get_doc("Project Charter",project_name[0][0])
            # for t in doc_a.get("project_risk"):
            #     doc_b.append("project_high_level_risks", {"risk": t.risk})
            #     doc_b.flags.ignore_mandatory = True
            #     doc_b.save(ignore_permissions=True)

        else:
            btea_doc = frappe.get_doc({
                "doctype":"Project Charter",
                "project": self.name,
                "project_manager": self.project_manager,
                "expected_start_date": self.start_date,
                "expected_end_date": self.end_date,
                "customer": self.customer,
                "project_sponsor": self.project_sponsor,
                "project_impact": "",
                "stakeholder": [
                              {
                                "doctype": "Stakeholder",
                                
                              }
                        ],
                "related_projects": "",
                "business_requirements": "",
                "project_objective": "",
                "scope": "",
                "scope_exclusions": "",
                "project_major_deliverables": [
                              {
                                "doctype": "Project Major Deliverables",
                                
                              }
                        ],
                "project_assumptions": "",
                "project_high_level_risks": [
                              {
                                "doctype": "Risks",
                                
                              }
                        ],
                "vendor": [
                              {
                                "doctype": "Project Vendor",
                                
                              }
                        ],
                "overall_project_budget": "",
            })
            btea_doc.flags.ignore_mandatory = True
            btea_doc.insert(ignore_permissions=True)
            return frappe.db.sql("select name from `tabProject Charter` where project='{0}'".format(self.name))[0][0]



def get_timeline_data(doctype, name):
    '''Return timeline for attendance'''
    return dict(frappe.db.sql('''select unix_timestamp(from_time), count(*)
        from `tabTimesheet Detail` where project=%s
            and from_time > date_sub(curdate(), interval 1 year)
            and docstatus < 2
            group by date(from_time)''', name))

def get_project_list(doctype, txt, filters, limit_start, limit_page_length=20):
    return frappe.db.sql('''select distinct project.*
        from tabProject project, `tabProject User` project_user
        where
            (project_user.user = %(user)s
            and project_user.parent = project.name)
            or project.owner = %(user)s
            order by project.modified desc
            limit {0}, {1}
        '''.format(limit_start, limit_page_length),
            {'user':frappe.session.user},
            as_dict=True,
            update={'doctype':'Project'})

def get_list_context(context=None):
    return {
        "show_sidebar": True,
        "show_search": True,
        'no_breadcrumbs': True,
        "title": _("Projects"),
        "get_list": get_project_list,
        "row_template": "templates/includes/projects/project_row.html"
    }

def get_users_for_project(doctype, txt, searchfield, start, page_len, filters):
    conditions = []
    return frappe.db.sql("""select name, concat_ws(' ', first_name, middle_name, last_name) 
        from `tabUser`
        where enabled=1
            and name not in ("Guest", "Administrator") 
            and ({key} like %(txt)s
                or full_name like %(txt)s)
            {fcond} {mcond}
        order by
            if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
            if(locate(%(_txt)s, full_name), locate(%(_txt)s, full_name), 99999),
            idx desc,
            name, full_name
        limit %(start)s, %(page_len)s""".format(**{
            'key': searchfield,
            'fcond': get_filters_cond(doctype, filters, conditions),
            'mcond': get_match_cond(doctype)
        }), {
            'txt': "%%%s%%" % txt,
            '_txt': txt.replace("%", ""),
            'start': start,
            'page_len': page_len
        })

@frappe.whitelist()
def get_cost_center_name(project):
    return frappe.db.get_value("Project", project, "cost_center")
