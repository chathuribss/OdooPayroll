from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Category codes used when a rule is left on "Automatic"
EARNING_CATEGORY_CODES = {"BASIC", "ALW", "PBSSALW"}
DEDUCTION_CATEGORY_CODES = {"DED"}


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    dist_include = fields.Boolean(
        string="Include in Distribution",
        default=True,
        help="Only the salary rules with this option are distributed between departments "
        "and get a journal entry. Untick it for rules like Gross, Net, EPF, ETF ...",
    )
    dist_type = fields.Selection(
        [
            ("auto", "Automatic (by Category)"),
            ("earning", "Earning (Dr Departments / Cr Payable)"),
            ("deduction", "Deduction (Dr Payable / Cr Departments)"),
        ],
        string="Distribution Type",
        default="auto",
        required=True,
        help="Automatic: Basic / Allowance categories are treated as earnings, Deduction category as "
        "deductions, any other category (Gross, Net, EPF, ETF ...) is skipped.",
    )
    dist_gl_code = fields.Char(string="GL Account Code", help="Default account of every department, e.g. 601110")
    dist_sys_code = fields.Char(string="SYS Code", help="SAP B1 account code, e.g. _SYS00000002427")
    dist_department_account_ids = fields.One2many(
        "hr.salary.rule.department.account", "salary_rule_id", string="Department Exceptions"
    )

    def _get_distribution_type(self):
        """Return "earning", "deduction" or "none" (not distributed)."""
        self.ensure_one()
        if not self.dist_include:
            return "none"
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

    def _get_distribution_account(self, department):
        """Return (gl_code, sys_code) of this rule for the department:
        the department exception when there is one, otherwise the account of the rule."""
        self.ensure_one()
        exception = self.dist_department_account_ids.filtered(lambda e: e.department_id == department)[:1]
        if exception:
            return exception.gl_code, exception.sys_code
        return self.dist_gl_code, self.dist_sys_code

    def _get_distribution_entry_name(self, department):
        """Name of a department journal line, e.g. "PBSS SMB Basic Salary"."""
        self.ensure_one()
        return "%s %s" % (department.name, self.name) if department else self.name


class HrSalaryRuleDepartmentAccount(models.Model):
    _name = "hr.salary.rule.department.account"
    _description = "Salary Rule Department Account"
    _order = "salary_rule_id, sequence, id"

    sequence = fields.Integer(default=10)
    salary_rule_id = fields.Many2one("hr.salary.rule", string="Salary Rule", required=True, ondelete="cascade")
    department_id = fields.Many2one("hr.department", string="Department", required=True, ondelete="cascade")
    sys_code = fields.Char(
        string="SYS Code",
        help="SAP B1 account code, e.g. _SYS00000002295. Required to validate a distribution using this line.",
    )
    gl_code = fields.Char(string="GL Account Code", required=True, help="e.g. 105618")

    @api.depends("department_id", "gl_code")
    def _compute_display_name(self):
        for line in self:
            line.display_name = "%s: %s" % (line.department_id.name or "", line.gl_code or "")

    @api.constrains("salary_rule_id", "department_id")
    def _check_unique_department(self):
        for rule in self.salary_rule_id:
            departments = rule.dist_department_account_ids.department_id
            if len(departments) != len(rule.dist_department_account_ids):
                raise ValidationError(_(
                    "A department is added more than once in the department exceptions of %s.", rule.name
                ))


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    dist_payable_gl_code = fields.Char(string="Payable GL Account Code", help="e.g. 205410")
    dist_payable_sys_code = fields.Char(string="Payable SYS Code", help="e.g. _SYS00000002354")
    dist_payable_gl_name = fields.Char(string="Payable GL Account Name", help="e.g. Staff Salary Payable")
    dist_payable_project_code = fields.Char(string="Payable Project", default="ADMIN")
    dist_payable_sbu_code = fields.Char(string="Payable SBU", default="0010")
