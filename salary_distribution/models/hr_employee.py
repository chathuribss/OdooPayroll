from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployeeSalaryDistribution(models.Model):
    _name = "hr.employee.salary.distribution"
    _description = "Employee Salary Distribution"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade", index=True
    )
    department_id = fields.Many2one("hr.department", string="Department", required=True)
    percentage = fields.Float(string="Percentage (%)", digits=(16, 2), required=True)
    company_id = fields.Many2one(related="employee_id.company_id", store=True)

    def init(self):
        # replaced by the python constraints below, drop them on databases where they were created
        for name in ("percentage_range", "employee_department_uniq"):
            self.env.cr.execute(
                'ALTER TABLE hr_employee_salary_distribution DROP CONSTRAINT IF EXISTS "%s"'
                % ("hr_employee_salary_distribution_" + name)
            )

    @api.constrains("employee_id", "department_id", "percentage")
    def _check_distribution_lines(self):
        for line in self:
            if line.percentage <= 0 or line.percentage > 100:
                raise ValidationError(_("The distribution percentage must be greater than 0 and at most 100."))
        for employee in self.employee_id:
            departments = employee.salary_distribution_ids.department_id
            if len(departments) != len(employee.salary_distribution_ids):
                duplicates = departments.filtered(
                    lambda d: len(employee.salary_distribution_ids.filtered(lambda l: l.department_id == d)) > 1
                )
                raise ValidationError(_(
                    "The department %(department)s is added more than once in the salary distribution of "
                    "%(employee)s. Use a single line with the total percentage.",
                    department=", ".join(duplicates.mapped("name")), employee=employee.name,
                ))
        self.employee_id._check_salary_distribution_total()


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    salary_distribution_ids = fields.One2many(
        "hr.employee.salary.distribution",
        "employee_id",
        string="Salary Distribution",
        groups="hr.group_hr_user",
    )
    salary_distribution_rule_ids = fields.Many2many(
        "salary.distribution.rule",
        "hr_employee_salary_distribution_rule_rel",
        "employee_id",
        "rule_id",
        string="Distribution Rules",
        groups="hr.group_hr_user",
    )
    salary_distribution_rule_line_ids = fields.Many2many(
        "salary.distribution.rule.line",
        string="Rule Departments",
        compute="_compute_salary_distribution_rule_line_ids",
        groups="hr.group_hr_user",
    )
    salary_distributed_percentage = fields.Float(
        string="Distributed to Other Departments (%)",
        compute="_compute_salary_distribution_percentage",
        groups="hr.group_hr_user",
    )
    salary_home_percentage = fields.Float(
        string="Remaining on Own Department (%)",
        compute="_compute_salary_distribution_percentage",
        groups="hr.group_hr_user",
    )

    @api.depends("salary_distribution_rule_ids.line_ids")
    def _compute_salary_distribution_rule_line_ids(self):
        for employee in self:
            employee.salary_distribution_rule_line_ids = employee.salary_distribution_rule_ids.line_ids

    @api.depends(
        "salary_distribution_ids.percentage",
        "salary_distribution_rule_ids.line_ids.percentage",
    )
    def _compute_salary_distribution_percentage(self):
        for employee in self:
            distributed = sum(split[1] for split in employee._get_salary_distribution_splits())
            employee.salary_distributed_percentage = distributed
            employee.salary_home_percentage = 100.0 - distributed

    def _get_salary_distribution_splits(self):
        """Return [(department, percentage, distribution rule or False)] combining the employee
        specific lines and every distribution rule of the employee. What is not distributed
        stays on the employee's own department."""
        self.ensure_one()
        employee = self.sudo()
        splits = [(d.department_id, d.percentage, False) for d in employee.salary_distribution_ids]
        for rule in employee.salary_distribution_rule_ids:
            splits += [(d.department_id, d.percentage, rule) for d in rule.line_ids]
        return splits

    @api.constrains("salary_distribution_rule_ids")
    def _check_salary_distribution_total(self):
        for employee in self:
            total = sum(split[1] for split in employee._get_salary_distribution_splits())
            if total > 100.0:
                raise ValidationError(_(
                    "The total salary distribution of %(employee)s is %(total)s%%, it cannot exceed 100%%.\n"
                    "(Employee specific departments + Distribution Rules)",
                    employee=employee.name, total="%g" % total,
                ))
