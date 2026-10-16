from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalaryDistributionRule(models.Model):
    _name = "salary.distribution.rule"
    _description = "Salary Distribution Rule"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(string="Rule Name", required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    line_ids = fields.One2many(
        "salary.distribution.rule.line", "rule_id", string="Departments", copy=True
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        "hr_employee_salary_distribution_rule_rel",
        "rule_id",
        "employee_id",
        string="Employees",
    )
    employee_count = fields.Integer(compute="_compute_employee_count")
    distributed_percentage = fields.Float(
        string="Distributed to Other Departments (%)", compute="_compute_percentages"
    )
    home_percentage = fields.Float(string="Remaining on Own Department (%)", compute="_compute_percentages")
    note = fields.Text()

    @api.constrains("employee_ids")
    def _check_employee_total(self):
        self.employee_ids._check_salary_distribution_total()

    @api.depends("employee_ids")
    def _compute_employee_count(self):
        for rule in self:
            rule.employee_count = len(rule.employee_ids)

    @api.depends("line_ids.percentage")
    def _compute_percentages(self):
        for rule in self:
            distributed = sum(rule.line_ids.mapped("percentage"))
            rule.distributed_percentage = distributed
            rule.home_percentage = 100.0 - distributed


class SalaryDistributionRuleLine(models.Model):
    _name = "salary.distribution.rule.line"
    _description = "Salary Distribution Rule Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    rule_id = fields.Many2one(
        "salary.distribution.rule", string="Rule", required=True, ondelete="cascade", index=True
    )
    department_id = fields.Many2one("hr.department", string="Distribution Department", required=True)
    percentage = fields.Float(string="Percentage (%)", digits=(16, 2), required=True)

    def init(self):
        # replaced by the python constraints below, drop them on databases where they were created
        for name in ("percentage_range", "rule_department_uniq"):
            self.env.cr.execute(
                'ALTER TABLE salary_distribution_rule_line DROP CONSTRAINT IF EXISTS "%s"'
                % ("salary_distribution_rule_line_" + name)
            )

    @api.depends("department_id", "percentage")
    def _compute_display_name(self):
        for line in self:
            line.display_name = "%s (%g%%)" % (line.department_id.name or "", line.percentage)

    @api.constrains("rule_id", "department_id", "percentage")
    def _check_total_percentage(self):
        for line in self:
            if line.percentage <= 0 or line.percentage > 100:
                raise ValidationError(_("The distribution percentage must be greater than 0 and at most 100."))
        for rule in self.rule_id:
            if len(rule.line_ids.department_id) != len(rule.line_ids):
                raise ValidationError(_(
                    "A department is added more than once in the distribution rule %s. "
                    "Use a single line with the total percentage.", rule.name,
                ))
            if sum(rule.line_ids.mapped("percentage")) > 100.0:
                raise ValidationError(_("The distribution rule %s exceeds 100%%.", rule.name))
            rule.employee_ids._check_salary_distribution_total()
