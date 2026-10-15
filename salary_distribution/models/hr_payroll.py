from odoo import fields, models

# Category codes used when a rule is left on "Automatic"
EARNING_CATEGORY_CODES = {"BASIC", "ALW", "PBSSALW"}
DEDUCTION_CATEGORY_CODES = {"DED"}


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    dist_type = fields.Selection(
        [
            ("auto", "Automatic (by Category)"),
            ("earning", "Earning (Dr Departments / Cr Payable)"),
            ("deduction", "Deduction (Dr Payable / Cr Departments)"),
            ("none", "Exclude"),
        ],
        string="Distribution Type",
        default="auto",
        required=True,
        help="Automatic: Basic / Allowance categories are treated as earnings, Deduction category as "
        "deductions, every other category (Gross, Net, EPF, ETF ...) is excluded.",
    )
    dist_gl_code = fields.Char(string="Expense G/L Code", help="e.g. 601110")
    dist_gl_name = fields.Char(string="Expense G/L Name", help="e.g. Basic Salary")

    def _get_distribution_type(self):
        self.ensure_one()
        if self.dist_type != "auto":
            return self.dist_type
        category = self.category_id
        while category:
            code = (category.code or "").upper()
            if code in EARNING_CATEGORY_CODES:
                return "earning"
            if code in DEDUCTION_CATEGORY_CODES:
                return "deduction"
            category = category.parent_id
        return "none"


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    dist_payable_gl_code = fields.Char(string="Payable G/L Code", help="e.g. 205410")
    dist_payable_gl_name = fields.Char(string="Payable G/L Name", help="e.g. Staff Salary Payable")
