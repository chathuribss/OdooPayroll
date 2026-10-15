from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    dist_project_code = fields.Char(
        string="Project Code", help="Project code shown on the distribution journal lines, e.g. ADMIN, CLINF."
    )
    dist_sbu_code = fields.Char(string="SBU", help="SBU code shown on the distribution journal lines, e.g. 0010.")
    dist_gl_code = fields.Char(
        string="Override G/L Code",
        help="When set, every journal line of this department uses this G/L account instead of the "
        "salary rule account (e.g. an inter-company account like 105618 PBSS SMB (Pvt) Ltd).",
    )
    dist_gl_name = fields.Char(string="Override G/L Name")
