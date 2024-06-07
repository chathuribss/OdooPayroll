from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class BankSheetReportWizard(models.TransientModel):
    _name = 'bank.sheet.report.wizard'
    _description = 'Bank Sheet Report Wizard'

    payslip_batch_id = fields.Many2one('hr.payslip.run')

    def generate_report(self):
        # Ensure `self.read()[0]` returns a dictionary
        struct_id = self.payslip_batch_id.slip_ids.mapped('struct_id')
        if len(struct_id) > 1:
            raise UserError(_("In this Batch has two Structures, You can Process Only One Structures"))
        name = ''
        if struct_id.name == 'PBSS Salary Structure':
            name = 'Salary Sheet'
        if struct_id.name == 'PBSS Allowance Structure':
            name = 'Allowance Sheet'

        return self.env.ref('send_payslips_by_email.bank_sheet_report_action').report_action(self.payslip_batch_id.id)

