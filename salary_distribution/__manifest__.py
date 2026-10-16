{
    "name": "Distribution",
    "version": "17.0.1.4.0",
    "category": "Human Resources/Payroll",
    "sequence": 1,
    "summary": "Distribute employee salary costs across departments and prepare SAP B1 salary journal entries",
    "description": """
Salary Cost Distribution
========================
* Share employee salary costs with other departments (Distribution Rules and/or employee specific
  Department + Percentage lines, max 100%). The rest stays with the employee's own department.
* Pick a payslip batch and compute the distribution for every salary rule
  (Basic Salary, Allowances, Deductions ...).
* Each salary rule holds its GL Account Code + SAP B1 SYS Code, with department exceptions.
* See totals per salary rule and department, the re-allocation flow and the journal entries
  (Dr / Cr, GL code, SYS code, Project, SBU) ready for SAP B1, and export them to Excel.
  No journal entry is created in Odoo.
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
