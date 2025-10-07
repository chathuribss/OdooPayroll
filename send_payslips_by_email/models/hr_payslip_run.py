import base64
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    report_name_val = fields.Char()

    def _get_filtered_slips(self):
        """Helper: return filtered slips based on wizard emp_type if passed via data context"""
        active_slips = self.slip_ids.filtered(lambda x: x.contract_id.state not in ['draft', 'new', 'cancel'])
        emp_type = self.env.context.get('emp_type') or (self._context.get('params', {}) or {}).get('emp_type')
        if emp_type:
            active_slips = active_slips.filtered(lambda s: s.employee_id.emp_type == emp_type)
        return active_slips

    def get_slip_chunks(self):
        slip_ids = self._get_filtered_slips().filtered(
            lambda slip: sum(
                slip.line_ids.filtered(
                    lambda line: line.appears_on_payslip and line.category_id.name == 'Net Salary'
                ).mapped('total')
            ) > 0
        )
        chunk_size = 15
        chunks = [slip_ids[i:i + chunk_size] for i in range(0, len(slip_ids), chunk_size)]

        grand_total = 0
        chunk_data = []
        for chunk in chunks:
            page_total = sum(
                sum(doc.line_ids.filtered(lambda l: l.appears_on_payslip and l.category_id.name == 'Net Salary').mapped('total'))
                for doc in chunk
            )
            grand_total += page_total
            chunk_data.append({
                'slips': chunk,
                'page_total': page_total,
            })
        return chunk_data, grand_total

    def get_grand_total(self):
        return sum(
            sum(doc.line_ids.filtered(lambda l: l.appears_on_payslip and l.category_id.name == 'Net Salary').mapped('total'))
            for doc in self._get_filtered_slips()
        )

    def get_net_total(self):
        return sum(
            self._get_filtered_slips().mapped('line_ids')
            .filtered(lambda l: l.appears_on_payslip and l.category_id.name == 'Net Salary')
            .mapped('amount')
        )

    def action_payslip_batch_send(self):
        active_slip_ids = self.slip_ids.filtered(lambda x: x.contract_id.state not in ['draft', 'new', 'cancel'])
        for rec in active_slip_ids:
            try:
                template_id = self.env['ir.model.data']._xmlid_to_res_id(
                    'send_payslips_by_email.mail_template_new_payslip_for_employee', raise_if_not_found=False
                )
            except ValueError:
                template_id = False
            if not template_id:
                raise UserError(_("Email Template must be selected in settings."))
            pdf_bin, file_format = self.env["ir.actions.report"]._render_qweb_pdf(
                "hr_payroll.report_payslip_lang", res_ids=rec.ids
            )
            pdf_name = re.sub(r"\W+", "", rec.employee_id.name) + "_Payslip.pdf"
            attach = self.env["ir.attachment"].create(
                {
                    "name": pdf_name,
                    "datas": base64.b64encode(pdf_bin),
                    "res_id": rec.id,
                    "res_model": "hr.payslip",
                    "type": "binary",
                }
            )
            template_data = {"attachment_ids": attach.ids}
            template = template_id and rec.env["mail.template"].browse(template_id)
            template.send_mail(rec.id, force_send=True, email_values=template_data)
        message = "Mail sent"
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {"title": _("Notification"), "message": message, "sticky": False},
        )

    def get_report_filename(self):
        """Custom method to set filename for bank sheet report"""
        # Check if we have emp_type stored on the record or in context
        emp_type = self.report_name_val or self.env.context.get('emp_type')

        if emp_type:
            emp_label = {
                'executive': 'Executive Level',
                'cluster_pm': 'Cluster Managers and Project Managers',
                'hod': 'HOD Team',
                'top_mgmt': 'Top Management'
            }.get(emp_type, 'All Employees')

            filename = f"{emp_label} {self.name or ''}"
            # Clean filename and return
            return "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).rstrip()

        # Fallback to default naming for other reports
        return f"Bank Sheet {self.name or ''}"

