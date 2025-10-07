from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BankSheetReportWizard(models.TransientModel):
    _name = 'bank.sheet.report.wizard'
    _description = 'Bank Sheet Report Wizard'

    payslip_batch_id = fields.Many2one('hr.payslip.run', string="Batch")
    emp_type = fields.Selection([
        ("executive", "Executive Level"),
        ("cluster_pm", "Cluster Managers & Project Managers"),
        ("hod", "HOD Team"),
        ("top_mgmt", "Top Management"),
    ], string="Employee Type")

    def generate_report(self):
        struct_ids = self.payslip_batch_id.slip_ids.mapped('struct_id')
        if len(struct_ids) > 1:
            raise UserError(_("This Batch has two Structures. You can Process Only One Structure"))

        # add emp_type into context
        return self.env.ref('send_payslips_by_email.bank_sheet_report_action').with_context(
            emp_type=self.emp_type
        ).report_action(self.payslip_batch_id.id)

