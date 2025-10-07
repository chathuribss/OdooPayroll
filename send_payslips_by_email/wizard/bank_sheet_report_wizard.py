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

        # Determine structure type
        struct_name = self.payslip_batch_id.slip_ids[:1].struct_id.name or ''
        prefix = "Allowance Sheet" if 'Allowance' in struct_name else "Salary Sheet"

        # Determine readable employee type
        emp_label = {
            'executive': 'Executive Level',
            'cluster_pm': 'Cluster Managers and Project Managers',
            'hod': 'HOD Team',
            'top_mgmt': 'Top Management'
        }.get(self.emp_type, 'All Employees')

        # Build final filename
        file_name = f"{prefix} {emp_label} {self.payslip_batch_id.name or ''}.pdf"

        # Generate report (your original working logic)
        action = self.env.ref('send_payslips_by_email.bank_sheet_report_action').with_context(
            emp_type=self.emp_type
        ).report_action(self.payslip_batch_id.id)

        # ✅ Only added this line for dynamic download name
        action['print_report_name'] = file_name

        return action
