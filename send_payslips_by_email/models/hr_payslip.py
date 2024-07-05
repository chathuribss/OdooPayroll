
from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError
from PyPDF2 import PdfFileWriter, PdfFileReader
import io
import base64
import re


class HRPayslip(models.Model):
    _name = "hr.payslip"
    _inherit = ["hr.payslip", "mail.thread", "mail.activity.mixin"]

    def get_salary_line_total(self, name):
        self.ensure_one()
        salary_lines = self.env['hr.payslip.line'].search([('slip_id', '=', self.id), ('name', '=', name)])
        return sum(line.total for line in salary_lines)

    # @api.depends('employee_id', 'struct_id', 'date_from', 'date_to')
    # def _compute_name(self):
    #     formated_date_cache = {}
    #     for slip in self.filtered(lambda p: p.employee_id and p.date_from and p.date_to):
    #         lang = slip.employee_id.lang or self.env.user.lang
    #         context = {'lang': lang}
    #         payslip_name = slip.struct_id.payslip_name or _('Salary Slip')
    #         del context
    #
    #         slip.name = '%(payslip_name)s - %(dates)s' % {
    #             'payslip_name': payslip_name,
    #             'dates': slip._get_period_name(formated_date_cache),
    #         }

    def payslip_send_mail(self):
        self.ensure_one()
        try:
            # template_id = self.env['ir.model.data']._xmlid_to_res_id(
            #     'send_payslips_by_email.mail_template_new_payslip_for_employee', raise_if_not_found=False
            # )
            template_id = self.env.ref('send_payslips_by_email.mail_template_new_payslip_for_employees').id
        except ValueError:
            template_id = False
        if not template_id:
            raise UserError(_("Email Template must be selected in settings."))
        template = template_id and self.env["mail.template"].browse(template_id)
        pdf_bin, file_format = self.env["ir.actions.report"]._render_qweb_pdf(
            "hr_payroll.report_payslip_lang", res_ids=self.ids
        )
        input_pdf = PdfFileReader(io.BytesIO(pdf_bin))
        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            output_pdf.addPage(input_pdf.getPage(page_num))

        # Set the password for the PDF
        if self.employee_id.slip_password:
            password = '1234'
            nic = self.employee_id.x_studio_nic
            if nic:
                numeric_string = ''.join(filter(str.isdigit, nic))
                last_four_digits = numeric_string[-4:]
                password = last_four_digits
            output_pdf.encrypt(password)

            # Save the PDF to a BytesIO object
            pdf_bytes = io.BytesIO()
            output_pdf.write(pdf_bytes)
            pdf_bytes.seek(0)
            pdf_bin = pdf_bytes.read()
        pdf_name = re.sub(r"\W+", "", self.employee_id.name) + "_Payslip.pdf"
        attach = self.env["ir.attachment"].create(
            {
                "name": pdf_name,
                "datas": base64.b64encode(pdf_bin),
                "res_id": self.id,
                "res_model": "hr.payslip",
                "type": "binary",
            }
        )
        template_data = {"attachment_ids": attach.ids}
        template.send_mail(self.id, force_send=True, email_values=template_data)
        message = "Mail sent"
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {"title": _("Notification"), "message": message, "sticky": False},
        )

    def send_payslip_by_email_action(self):
        for rec in self:
            try:
                template_id = self.env['ir.model.data']._xmlid_to_res_id(
                    'send_payslips_by_email.mail_template_new_payslip_for_employees', raise_if_not_found=False
                )
            except ValueError:
                template_id = False
            if not template_id:
                raise UserError(_("Email Template must be selected in settings."))
            template = template_id and rec.env["mail.template"].browse(template_id)
            pdf_bin, file_format = self.env["ir.actions.report"]._render_qweb_pdf(
                "hr_payroll.report_payslip_lang", res_ids=rec.ids
            )
            input_pdf = PdfFileReader(io.BytesIO(pdf_bin))
            output_pdf = PdfFileWriter()

            for page_num in range(input_pdf.getNumPages()):
                output_pdf.addPage(input_pdf.getPage(page_num))

            # Set the password for the PDF
            if rec.employee_id.slip_password:
                password = '1234'
                nic = rec.employee_id.x_studio_nic
                if nic:
                    numeric_string = ''.join(filter(str.isdigit, nic))
                    last_four_digits = numeric_string[-4:]
                    password = last_four_digits
                output_pdf.encrypt(password)

                # Save the PDF to a BytesIO object
                pdf_bytes = io.BytesIO()
                output_pdf.write(pdf_bytes)
                pdf_bytes.seek(0)
                pdf_bin = pdf_bytes.read()
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
            template.send_mail(rec.id, force_send=True, email_values=template_data)
        message = "Mail sent"
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {"title": _("Notification"), "message": message, "sticky": False},
        )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    choose_mail_template = fields.Many2one(
        "mail.template",
        string="Mail Template For Payroll",
        config_parameter="send_payslips_by_email.choose_mail_template",
    )

    choose_mail_template_for_employee = fields.Many2one(
        "mail.template",
        string="Mail Template For Employee",
        config_parameter="send_payslips_by_email.choose_mail_template_for_employee",
    )
