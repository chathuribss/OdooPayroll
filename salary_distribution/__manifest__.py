{
    "name": "Distribution",
    "version": "17.0.1.0.0",
    "category": "Human Resources/Payroll",
    "sequence": 1,
    "summary": "Distribute employee salary costs across departments and build salary journal entries per salary rule",
    "description": """
Salary Cost Distribution
========================
* Define on each employee which other departments share his salary cost (Department + Percentage).
  The remaining percentage stays with the employee's own department.
* Pick a payslip batch and compute the distribution for every salary rule
  (Basic Salary, Allowances, Deductions ...).
* See the totals per salary rule and department, the re-allocation flow
  and journal entries (Dr / Cr) ready to be posted, and export them to Excel.
""",
    "author": "Perfect Business Solution Services (Pvt) Ltd",
    "website": "https://www.perfectbss.com",
    "license": "OPL-1",
    "depends": ["hr", "hr_payroll"],
    "data": [
        "security/ir.model.access.csv",
        "views/salary_distribution_rule_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_department_views.xml",
        "views/hr_payroll_views.xml",
        "views/salary_distribution_line_views.xml",
        "views/salary_distribution_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "salary_distribution/static/src/scss/salary_distribution.scss",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
}
