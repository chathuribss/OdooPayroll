from odoo import fields, models

DIST_TYPES = [("earning", "Earning"), ("deduction", "Deduction")]


class SalaryDistributionLine(models.Model):
    _name = "salary.distribution.line"
    _description = "Salary Distribution Detail"
    _order = "rule_sequence, salary_rule_id, department_id, employee_id"

    distribution_id = fields.Many2one(
        "salary.distribution", string="Distribution", required=True, ondelete="cascade", index=True
    )
    payslip_id = fields.Many2one("hr.payslip", string="Payslip", ondelete="set null")
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    home_department_id = fields.Many2one("hr.department", string="Employee Department")
    department_id = fields.Many2one("hr.department", string="Charged Department")
    salary_rule_id = fields.Many2one("hr.salary.rule", string="Salary Rule", required=True)
    rule_sequence = fields.Integer(related="salary_rule_id.sequence", store=True)
    category_id = fields.Many2one(related="salary_rule_id.category_id", store=True, string="Category")
    dist_type = fields.Selection(DIST_TYPES, string="Type", required=True)
    percentage = fields.Float(string="Share (%)", digits=(16, 2), group_operator=False)
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    distribution_source = fields.Selection(
        [("custom", "Employee Specific"), ("rule", "Distribution Rule"), ("none", "Own Department")],
        string="Source",
    )
    distribution_rule_id = fields.Many2one("salary.distribution.rule", string="Distribution Rule", ondelete="set null")
    is_reallocated = fields.Boolean(
        string="Re-allocated", help="Amount moved from the employee's department to another department."
    )
    batch_id = fields.Many2one(related="distribution_id.batch_id", store=True)
    date_end = fields.Date(related="distribution_id.date_end", store=True, string="Period")
    company_id = fields.Many2one(related="distribution_id.company_id", store=True)
    currency_id = fields.Many2one(related="distribution_id.currency_id")


class SalaryDistributionJournal(models.Model):
    _name = "salary.distribution.journal"
    _description = "Salary Distribution Journal Line"
    _order = "sequence, id"

    distribution_id = fields.Many2one(
        "salary.distribution", string="Distribution", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer()
    salary_rule_id = fields.Many2one("hr.salary.rule", string="Journal Entry")
    dist_type = fields.Selection(DIST_TYPES, string="Type")
    gl_code = fields.Char(string="GL Account Code")
    sys_code = fields.Char(string="SYS Code")
    gl_name = fields.Char(string="Entry Name", help="Department + salary rule, e.g. PBSS SMB Basic Salary.")
    missing_account = fields.Boolean(
        string="Missing Account", help="The GL Account Code or the SYS Code is not configured."
    )
    debit = fields.Monetary(currency_field="currency_id")
    credit = fields.Monetary(currency_field="currency_id")
    remarks = fields.Char()
    department_id = fields.Many2one("hr.department", string="Department")
    project_code = fields.Char(string="Project")
    sbu_code = fields.Char(string="SBU")
    is_payable = fields.Boolean(string="Payable Line")
    currency_id = fields.Many2one(related="distribution_id.currency_id")
