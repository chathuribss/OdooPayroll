from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    dist_sequence = fields.Integer(
        string="Journal Sequence", default=10, help="Order of the department lines in the journal entries."
    )
    dist_project_code = fields.Char(
        string="Project Code", help="Project code sent with the journal lines, e.g. ADMIN, CLINF."
    )
    dist_sbu_code = fields.Char(string="SBU", help="SBU code sent with the journal lines, e.g. 0010.")
