from odoo import models, fields, api
import xlsxwriter
import base64
from io import BytesIO


class PayslipBatchWizard(models.TransientModel):
    _name = 'payslip.batch.wizard'
    _description = 'Payslip Batch Wizard'

    batch_id = fields.Many2one('hr.payslip.run', string='Payslip Batch', required=True)

    def print_report(self):
        # Call the function to generate and download the report
        return self._generate_excel_report()

    def _generate_excel_report(self):
        # Fetch payslips related to the selected batch
        payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', self.batch_id.id)])

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Define formats
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': 'blue', 'align': 'center', 'valign': 'vcenter',
            'font_size': 20
        })

        column_header_format = workbook.add_format({
            'bold': True, 'font_color': 'black', 'bg_color': 'yellow', 'align': 'center', 'valign': 'vcenter'
        })

        text_format = workbook.add_format({
            'font_color': 'black', 'align': 'left', 'valign': 'vcenter'
        })
        amount_format = workbook.add_format({
            'font_color': 'black', 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'
        })
        total_format = workbook.add_format({
            'bold': True, 'font_color': 'black', 'bg_color': 'green', 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'
        })

        # Set column widths
        worksheet.set_column('A:A', 10)  # EMP No
        worksheet.set_column('B:B', 20)  # Department
        worksheet.set_column('C:C', 20)  # Pay Slip Name
        worksheet.set_column('D:D', 15)  # NIC
        worksheet.set_column('E:E', 20)  # Peoples Bank Ac No
        worksheet.set_column('F:F', 20)  # Designation
        worksheet.set_column('G:Y', 15)  # Salary components and totals

        # Set header row height
        worksheet.set_row(0, 30)  # Adjust the height of the first row (headers)

        # Add header
        header_text = f"PBSS Salary Sheet for {self.batch_id.name}"
        worksheet.merge_range('A1:Y1', header_text, header_format)

        # Define the headers
        headers = [
            'EMP No', 'Department', 'Pay Slip Name', 'NIC', 'Peoples Bank Ac No', 'Designation',
            'Basic Salary', 'Travelling Allowance', 'COL Allowance', 'Vehicle Rent Tax Applicable',
            'Gross Salary', 'PAYE Applicable Salary', 'ETF 3%', 'EPF 20%', 'EPF 12%', 'EPF 8%',
            'PAYE', 'Scholarship Contribution', 'Salary Advance', 'Staff Loan', 'Late Attendance',
            'NO Pay', 'Dialog', 'Welfare', 'Net Salary'
        ]

        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(1, col, header, column_header_format)

        # Initialize row and column totals
        row = 2
        col_totals = [0] * len(headers)

        # Write data rows
        for payslip in payslips:
            employee = payslip.employee_id

            # Salary components
            salary_components = {
                'Basic Salary': payslip.get_salary_line_total('Basic Salary'),
                'Travelling Allowance': payslip.get_salary_line_total('Travelling Allowance'),
                'COL Allowance': payslip.get_salary_line_total('COL Allowance'),
                'Vehicle Rent Tax Applicable': payslip.get_salary_line_total('Vehicle Rent Tax Applicable'),
                'Gross Salary': payslip.get_salary_line_total('Gross Salary'),
                'PAYE Applicable Salary': payslip.get_salary_line_total('PAYE Applicable Salary'),
                'ETF 3%': payslip.get_salary_line_total('ETF 3%'),
                'EPF 20%': payslip.get_salary_line_total('EPF 20%'),
                'EPF 12%': payslip.get_salary_line_total('EPF 12%'),
                'EPF 8%': payslip.get_salary_line_total('EPF 8%'),
                'PAYE': payslip.get_salary_line_total('Paye'),
                'Scholarship Contribution': payslip.get_salary_line_total('Scholarship Contribution'),
                'Salary Advance': payslip.get_salary_line_total('Salary Advance'),
                'Staff Loan': payslip.get_salary_line_total('Staff Loan'),
                'Late Attendance': payslip.get_salary_line_total('Late Attendance'),
                'NO Pay': payslip.get_salary_line_total('NO Pay'),
                'Dialog': payslip.get_salary_line_total('Dialog'),
                'Welfare': payslip.get_salary_line_total('Welfare'),
                'Net Salary': payslip.get_salary_line_total('Net Salary')
            }

            # Write employee and salary component details
            details = [
                          employee.barcode or '', employee.department_id.name or '', payslip.name or '',
                          employee.x_studio_nic or '', employee.x_studio_savings_account_number or '',
                          employee.job_id.name or ''
                      ] + [salary_components.get(key, 0) for key in
                           headers[6:]]  # Skip first 6 header columns for employee details

            for col, detail in enumerate(details):
                if col < 6:
                    worksheet.write(row, col, detail, text_format)
                else:
                    worksheet.write(row, col, detail, amount_format)

            # Update column totals
            for col, key in enumerate(headers[6:], start=6):
                col_totals[col] += salary_components.get(key, 0)

            row += 1

        # Write totals
        worksheet.write(row, 5, 'Total', total_format)
        for col in range(6, len(headers)):
            worksheet.write(row, col, col_totals[col], total_format)

        workbook.close()
        output.seek(0)

        # Encode the file
        file_data = base64.b64encode(output.read())
        file_name = f'Payslip_Batch_Report_{self.batch_id.name}.xlsx'

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': file_data,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })

        # Download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    def get_salary_line_total(self, name):
        self.ensure_one()
        salary_lines = self.env['hr.payslip.line'].search([('slip_id', '=', self.id), ('name', '=', name)])
        return sum(line.total for line in salary_lines)