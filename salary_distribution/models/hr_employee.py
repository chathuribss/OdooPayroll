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

    _sql_constraints = [
        (
            "percentage_range",
            "CHECK(percentage > 0 AND percentage <= 100)",
            "The distribution percentage must be greater than 0 and at most 100.",
        ),
        (
            "employee_department_uniq",
            "UNIQUE(employee_id, department_id)",
            "A department can only be used once in an employee's salary distribution.",
        ),
    ]

    @api.constrains("employee_id", "percentage")
    def _check_total_percentage(self):
        for employee in self.employee_id:
            if sum(employee.salary_distribution_ids.mapped("percentage")) > 100.0:
                raise ValidationError(
                    _("The salary distribution of %s exceeds 100%%.", employee.name)
                )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    salary_distribution_ids = fields.One2many(
        "hr.employee.salary.distribution",
        "employee_id",
        string="Salary Distribution",
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

    @api.depends("salary_distribution_ids.percentage")
    def _compute_salary_distribution_percentage(self):
        for employee in self:
            distributed = sum(employee.salary_distribution_ids.mapped("percentage"))
            employee.salary_distributed_percentage = distributed
            employee.salary_home_percentage = 100.0 - distributed
