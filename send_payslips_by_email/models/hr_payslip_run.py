import base64
import re

from odoo import _, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _name = "hr.payslip.run"
    _inherit = ["hr.payslip.run", "mail.thread", "mail.activity.mixin"]

    def get_slip_chunks(self):
        """ Returns a list of slip chunks, each with a page total, and a grand total """
        slip_ids = self.slip_ids.filtered(
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
            page_total = 0
            for doc in chunk:
                net_totals = doc.line_ids.filtered(
                    lambda line: line.appears_on_payslip and line.category_id.name == 'Net Salary'
                ).mapped('total')
                page_total += sum(net_totals)

            grand_total += page_total
            chunk_data.append({
                'slips': chunk,
                'page_total': page_total,
            })

        return chunk_data, grand_total

    def get_grand_total(self):
        """ Calculate the grand total for all slips """
        grand_total = 0
        for doc in self.slip_ids.filtered(
            lambda slip: sum(
                slip.line_ids.filtered(
                    lambda line: line.appears_on_payslip and line.category_id.name == 'Net Salary'
                ).mapped('total')
            ) > 0
        ):
            net_totals = doc.line_ids.filtered(
                lambda line: line.appears_on_payslip and line.category_id.name == 'Net Salary'
            ).mapped('total')
            grand_total += sum(net_totals)
        return grand_total



    def get_net_total(self):
        net_total = sum(self.slip_ids.mapped('line_ids').filtered(lambda line: line.appears_on_payslip and line.category_id.name == 'Net Salary').mapped('amount'))
        return net_total

    def action_payslip_batch_send(self):
        for rec in self.slip_ids:
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
