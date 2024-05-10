{
    "name": "Send Payslip By Email",
    "summary": """
    Send Payslip By Email with pdf attchment
      """,
    "category": "Payroll",
    "version": "17.0.0.0.0",
    "sequence": 1,
    "author": "Perfect Business Solution Services (Pvt) Ltd",
    "license": "OPL-1",
    "website": "https://www.perfectbss.com",
    "description": """
    Just One Click and it's Gone!
   Save a lot of time by simplifying the process of
  dispatching payslips to your much valued employees.
 Use less effort and reduce delays in serving your employees.
""",
    "depends": ["hr_holidays", "hr", "mail", "hr_payroll", "hr_payroll_holidays"],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_employee.xml",
        "wizard/payslip_wizard.xml",
        "views/view_hr_payslip.xml",
        "views/pbss_report_payslip_templates.xml",
        "views/view_hr_payslip_run.xml",
        "views/hr_employee_view.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
