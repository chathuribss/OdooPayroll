from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BankSheetReportWizard(models.TransientModel):
    _name = 'bank.sheet.report.wizard'
    _description = 'Bank Sheet Report Wizard'

    payslip_batch_id = fields.Many2one('hr.payslip.run', string="Batch", required=True)
    emp_type = fields.Selection([
        ("executive", "Executive Level"),
        ("cluster_pm", "Cluster Managers & Project Managers"),
        ("hod", "HOD Team"),
        ("top_mgmt", "Top Management"),
    ], string="Employee Type")

    def _get_report_filename(self):
        """Return dynamic file name like 'Salary Sheet Executive Level August 2025.pdf'."""
        struct_name = self.payslip_batch_id.slip_ids[:1].struct_id.name or ''
        emp_type = self.emp_type

        prefix = "Allowance Sheet" if 'Allowance' in struct_name else "Salary Sheet"

        emp_label = {
            'executive': 'Executive Level',
            'cluster_pm': 'Cluster Managers and Project Managers',
            'hod': 'HOD Team',
            'top_mgmt': 'Top Management'
        }.get(emp_type, 'All Employees')

        file_name = f"{prefix} {emp_label} {self.payslip_batch_id.name or ''}.pdf"
        return file_name

    def generate_report(self):
        struct_ids = self.payslip_batch_id.slip_ids.mapped('struct_id')
        if len(struct_ids) > 1:
            raise UserError(_("This Batch has two Structures. You can Process Only One Structure"))

        file_name = self._get_report_filename()

        # Correct: report_action should keep report_name fixed and use print_report_name for file name
        action = self.env.ref('send_payslips_by_email.bank_sheet_report_action').report_action(
            self.payslip_batch_id
        )
        action['context'] = dict(self.env.context, emp_type=self.emp_type)
        action['print_report_name'] = file_name  # ✅ correct key for downloaded file name
        return action
