{
    'name': 'PBSS Employee Contract Update',
    "version": "17.0.0.0.1",
    'category': 'HR',
    'summary': 'Wizard to update employee contract details from API data',
    'author': 'PBSS',
    'depends': ['hr', 'hr_contract', 'hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/contract_update_wizard_view.xml',
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
