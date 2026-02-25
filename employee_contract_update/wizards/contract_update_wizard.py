from odoo import api, fields, models
import requests
import json
from odoo.exceptions import UserError, AccessError


class ContractUpdateWizard(models.TransientModel):
    _name = 'contract.update.wizard'
    _description = 'Employee Contract Update Wizard'

    month = fields.Selection([
        ('0', 'January'), ('1', 'February'), ('2', 'March'), ('3', 'April'),
        ('4', 'May'), ('5', 'June'), ('6', 'July'), ('7', 'August'),
        ('8', 'September'), ('9', 'October'), ('10', 'November'), ('11', 'December')
    ], string="Month", default='0', required=True)

    def update_contracts(self):
        api_url = "http://pbsshrm.ddns.net:8044/api/AttMange/GetAttendanceCounts"
        payload = {
            "MonthNo": int(self.month),
            "UserName": "Admin",
            "Password": "compaq123"
        }
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(api_url, data=json.dumps(payload), headers=headers)
            if response.status_code != 200:
                raise UserError("API request failed: " + response.text)

            data = response.json()
            if not data:
                raise UserError("Invalid API response format")

            hr_employee = self.env['hr.employee']
            hr_contract = self.env['hr.contract']

            for record in data:
                emp = hr_employee.search([('barcode', '=', record.get('documentEmployeeNo'))])

                if emp:
                    contracts = hr_contract.search([
                        ('employee_id', '=', emp.id),
                        ('state', '=', 'open')
                    ])

                    if len(contracts) == 0:
                        raise UserError(f"No running contract for {emp.name}.")
                    elif len(contracts) > 1:
                        raise UserError(f"Multiple running contracts for {emp.name}, please resolve manually.")

                    contract = contracts[0]
                    if emp.x_studio_contracts_interns_others:
                        contract.update({
                            'x_studio_late_attendance_minutes': record.get('lm', ''),
                            'x_studio_no_pay_day_count': record.get('npd', ''),
                        })
                    else:
                        contract.update({
                            'x_studio_late_attendance_minutes': record.get('lm', ''),
                            'x_studio_no_pay_day_count': record.get('npd', ''),
                        })


        except Exception as e:
            raise UserError(f"Error updating contracts: {str(e)}")
