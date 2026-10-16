import base64
import io
from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang, xlsxwriter

UNDEFINED_DEPARTMENT = "Undefined"


class SalaryDistribution(models.Model):
    _name = "salary.distribution"
    _description = "Salary Distribution"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_end desc, id desc"

    name = fields.Char(required=True, tracking=True)
    batch_id = fields.Many2one(
        "hr.payslip.run",
        string="Payslip Batch",
        required=True,
        tracking=True,
        domain="[('company_id', 'in', allowed_company_ids)]",
    )
    date_start = fields.Date(related="batch_id.date_start", store=True, string="Date From")
    date_end = fields.Date(related="batch_id.date_end", store=True, string="Date To")
    company_id = fields.Many2one(related="batch_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    state = fields.Selection(
        [("draft", "Draft"), ("computed", "Computed"), ("validated", "Validated")],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    line_ids = fields.One2many("salary.distribution.line", "distribution_id", string="Details", copy=False)
    journal_line_ids = fields.One2many(
        "salary.distribution.journal", "distribution_id", string="Journal Lines", copy=False
    )
    note = fields.Html()

    employee_count = fields.Integer(compute="_compute_totals")
    department_count = fields.Integer(compute="_compute_totals")
    total_earning = fields.Monetary(compute="_compute_totals", string="Total Earnings")
    total_deduction = fields.Monetary(compute="_compute_totals", string="Total Deductions")
    total_reallocated = fields.Monetary(compute="_compute_totals", string="Re-allocated")
    summary_html = fields.Html(compute="_compute_html", sanitize=False)
    journal_html = fields.Html(compute="_compute_html", sanitize=False)

    @api.onchange("batch_id")
    def _onchange_batch_id(self):
        if self.batch_id and not self.name:
            self.name = _("Distribution - %s", self.batch_id.name)

    @api.depends("line_ids.amount", "line_ids.dist_type", "line_ids.is_reallocated")
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.employee_count = len(lines.employee_id)
            rec.department_count = len(set(lines.mapped(lambda l: l.department_id.id)))
            rec.total_earning = sum(lines.filtered(lambda l: l.dist_type == "earning").mapped("amount"))
            rec.total_deduction = sum(lines.filtered(lambda l: l.dist_type == "deduction").mapped("amount"))
            rec.total_reallocated = sum(lines.filtered("is_reallocated").mapped("amount"))

    @api.depends("line_ids", "journal_line_ids")
    def _compute_html(self):
        for rec in self:
            rec.summary_html = rec._render_summary_html() if rec.line_ids else False
            rec.journal_html = rec._render_journal_html() if rec.journal_line_ids else False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_compute(self):
        for rec in self:
            if rec.state == "validated":
                raise UserError(_("A validated distribution cannot be recomputed. Reset it to draft first."))
            slips = rec.batch_id.slip_ids.filtered(lambda s: s.state != "cancel")
            if not slips:
                raise UserError(_("The batch %s has no payslips to distribute.", rec.batch_id.name))
            rec.line_ids.unlink()
            rec.journal_line_ids.unlink()
            self.env["salary.distribution.line"].create(rec._prepare_distribution_lines(slips))
            self.env["salary.distribution.journal"].create(rec._prepare_journal_lines())
            rec.state = "computed"
        return True

    def action_validate(self):
        self.filtered(lambda r: r.state == "computed").write({"state": "validated"})

    def action_reset_draft(self):
        self.line_ids.unlink()
        self.journal_line_ids.unlink()
        self.write({"state": "draft"})

    def unlink(self):
        if any(rec.state == "validated" for rec in self):
            raise UserError(_("You cannot delete a validated distribution."))
        return super().unlink()

    def action_open_analysis(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("salary_distribution.action_salary_distribution_line")
        action["domain"] = [("distribution_id", "=", self.id)]
        action["context"] = {"search_default_group_rule": 1}
        action["display_name"] = _("Analysis - %s", self.name)
        return action

    def action_open_journal_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Lines - %s", self.name),
            "res_model": "salary.distribution.journal",
            "view_mode": "tree",
            "domain": [("distribution_id", "=", self.id)],
            "context": {"group_by": "salary_rule_id"},
        }

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Compute the distribution before exporting it."))
        file_name = "%s.xlsx" % self.name.replace("/", "-")
        attachment = self.env["ir.attachment"].create({
            "name": file_name,
            "datas": base64.b64encode(self._generate_xlsx()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _prepare_distribution_lines(self, slips):
        """Split every distributable payslip line of each employee between the departments
        configured on the employee; whatever is left stays on the employee's own department."""
        self.ensure_one()
        currency = self.currency_id
        vals_list = []
        rule_types = {}
        for slip in slips:
            employee = slip.employee_id
            home_department = employee.department_id
            splits = employee._get_salary_distribution_splits()
            home_percentage = 100.0 - sum(split[1] for split in splits)
            for payslip_line in slip.line_ids:
                rule = payslip_line.salary_rule_id
                if rule not in rule_types:
                    rule_types[rule] = rule._get_distribution_type()
                dist_type = rule_types[rule]
                if dist_type == "none" or currency.is_zero(payslip_line.total):
                    continue
                amount = payslip_line.total if dist_type == "earning" else abs(payslip_line.total)
                common = {
                    "distribution_id": self.id,
                    "payslip_id": slip.id,
                    "employee_id": employee.id,
                    "home_department_id": home_department.id,
                    "salary_rule_id": rule.id,
                    "dist_type": dist_type,
                }
                allocated = 0.0
                for department, percentage, dist_rule in splits:
                    part = currency.round(amount * percentage / 100.0)
                    if currency.is_zero(part):
                        continue
                    allocated += part
                    vals_list.append(dict(
                        common,
                        department_id=department.id,
                        percentage=percentage,
                        amount=part,
                        is_reallocated=department != home_department,
                        distribution_source="rule" if dist_rule else "custom",
                        distribution_rule_id=dist_rule.id if dist_rule else False,
                    ))
                # the remainder absorbs rounding so the employee total always matches the payslip
                remainder = currency.round(amount - allocated)
                if not currency.is_zero(remainder):
                    vals_list.append(dict(
                        common,
                        department_id=home_department.id,
                        percentage=home_percentage,
                        amount=remainder,
                        is_reallocated=False,
                        distribution_source="none",
                    ))
        return vals_list

    def _prepare_journal_lines(self):
        """One balanced journal entry per salary rule, like the accounting salary sheet:
        earnings debit each department and credit the payable,
        deductions debit the payable and credit each department."""
        self.ensure_one()
        period = self.date_end.strftime("%B %Y") if self.date_end else ""
        vals_list = []
        sequence = 0
        for rule, dist_type, dept_amounts in self._get_rule_department_amounts():
            remarks = "%s %s" % (rule.name, period)
            total = sum(dept_amounts.values())
            structure = rule.struct_id
            payable_vals = {
                "gl_code": structure.dist_payable_gl_code or "",
                "gl_name": structure.dist_payable_gl_name or _("Staff Salary Payable"),
                "is_payable": True,
                **self._debit_credit(total, debit_side=dist_type == "deduction"),
            }
            department_vals = []
            for department, amount in dept_amounts.items():
                department_vals.append({
                    "gl_code": department.dist_gl_code or rule.dist_gl_code or "",
                    "gl_name": department.dist_gl_name or rule.dist_gl_name or rule.name,
                    "department_id": department.id,
                    "project_code": department.dist_project_code or department.name or UNDEFINED_DEPARTMENT,
                    "sbu_code": department.dist_sbu_code or "",
                    **self._debit_credit(amount, debit_side=dist_type == "earning"),
                })
            ordered = department_vals + [payable_vals] if dist_type == "earning" else [payable_vals] + department_vals
            for vals in ordered:
                sequence += 1
                vals_list.append(dict(
                    vals,
                    distribution_id=self.id,
                    sequence=sequence,
                    salary_rule_id=rule.id,
                    dist_type=dist_type,
                    remarks=remarks,
                ))
        return vals_list

    @api.model
    def _debit_credit(self, amount, debit_side):
        # a negative amount goes to the opposite side
        if amount < 0:
            amount, debit_side = -amount, not debit_side
        return {"debit": amount, "credit": 0.0} if debit_side else {"debit": 0.0, "credit": amount}

    def _get_rule_department_amounts(self):
        """Return [(rule, dist_type, {department: amount})] ordered by rule sequence
        with departments ordered by name."""
        self.ensure_one()
        grouped = defaultdict(lambda: defaultdict(float))
        types = {}
        for line in self.line_ids:
            grouped[line.salary_rule_id][line.department_id] += line.amount
            types[line.salary_rule_id] = line.dist_type
        result = []
        for rule in sorted(grouped, key=lambda r: (types[r] != "earning", r.sequence, r.id)):
            amounts = grouped[rule]
            ordered = dict(sorted(amounts.items(), key=lambda kv: self._department_label(kv[0])))
            result.append((rule, types[rule], ordered))
        return result

    def _get_departments(self):
        departments = self.line_ids.mapped("department_id")
        result = sorted(departments, key=self._department_label)
        if any(not line.department_id for line in self.line_ids):
            result.append(self.env["hr.department"])
        return result

    @api.model
    def _department_label(self, department):
        return department.name or UNDEFINED_DEPARTMENT

    def _get_reallocation_flow(self):
        flow = defaultdict(lambda: {"amount": 0.0, "employees": set()})
        for line in self.line_ids.filtered("is_reallocated"):
            key = (line.home_department_id, line.department_id, line.dist_type)
            flow[key]["amount"] += line.amount
            flow[key]["employees"].add(line.employee_id.id)
        return sorted(
            flow.items(),
            key=lambda kv: (self._department_label(kv[0][0]), self._department_label(kv[0][1]), kv[0][2]),
        )

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------
    def _fmt(self, amount, blank_zero=True):
        if blank_zero and self.currency_id.is_zero(amount):
            return Markup('<span class="o_sd_zero">-</span>')
        return formatLang(self.env, amount, digits=2)

    def _render_summary_html(self):
        self.ensure_one()
        departments = self._get_departments()
        rows = self._get_rule_department_amounts()
        currency = self.currency_id.symbol or ""

        cards = [
            (_("Employees"), str(self.employee_count), "fa-users", "o_sd_card_blue"),
            (_("Departments"), str(self.department_count), "fa-sitemap", "o_sd_card_purple"),
            (_("Total Earnings"), self._fmt(self.total_earning, False), "fa-arrow-up", "o_sd_card_green"),
            (_("Total Deductions"), self._fmt(self.total_deduction, False), "fa-arrow-down", "o_sd_card_red"),
            (_("Re-allocated"), self._fmt(self.total_reallocated, False), "fa-random", "o_sd_card_orange"),
        ]
        html = Markup('<div class="o_sd_report"><div class="o_sd_cards">')
        for label, value, icon, css in cards:
            html += Markup(
                '<div class="o_sd_card %s"><i class="fa %s"></i><div><div class="o_sd_card_value">%s</div>'
                '<div class="o_sd_card_label">%s</div></div></div>'
            ) % (css, icon, value, label)
        html += Markup("</div>")

        # Salary rule x department matrix
        html += Markup('<h4 class="o_sd_title">%s <small>(%s)</small></h4>') % (
            _("Salary Rules by Department"), currency)
        html += Markup('<div class="o_sd_scroll"><table class="o_sd_table"><thead><tr><th class="o_sd_sticky">%s</th>') % _(
            "Salary Rule")
        for department in departments:
            html += Markup("<th>%s</th>") % self._department_label(department)
        html += Markup('<th class="o_sd_total_col">%s</th></tr></thead><tbody>') % _("Total")

        net_by_department = defaultdict(float)
        for dist_type, title in (("earning", _("Earnings")), ("deduction", _("Deductions"))):
            section = [(rule, amounts) for rule, rtype, amounts in rows if rtype == dist_type]
            if not section:
                continue
            html += Markup('<tr class="o_sd_section o_sd_section_%s"><td colspan="%s">%s</td></tr>') % (
                dist_type, len(departments) + 2, title)
            subtotal = defaultdict(float)
            for rule, amounts in section:
                html += Markup('<tr><td class="o_sd_sticky">%s</td>') % rule.name
                for department in departments:
                    amount = amounts.get(department, 0.0)
                    subtotal[department] += amount
                    html += Markup("<td>%s</td>") % self._fmt(amount)
                html += Markup('<td class="o_sd_total_col">%s</td></tr>') % self._fmt(sum(amounts.values()))
            html += Markup('<tr class="o_sd_subtotal"><td class="o_sd_sticky">%s</td>') % _("Total %s", title)
            for department in departments:
                html += Markup("<td>%s</td>") % self._fmt(subtotal[department])
                net_by_department[department] += subtotal[department] * (1 if dist_type == "earning" else -1)
            html += Markup('<td class="o_sd_total_col">%s</td></tr>') % self._fmt(sum(subtotal.values()))

        html += Markup('</tbody><tfoot><tr><td class="o_sd_sticky">%s</td>') % _("Net Cost")
        for department in departments:
            html += Markup("<td>%s</td>") % self._fmt(net_by_department[department])
        html += Markup('<td class="o_sd_total_col">%s</td></tr></tfoot></table></div>') % self._fmt(
            sum(net_by_department.values()))

        # Re-allocation flow
        flow = self._get_reallocation_flow()
        if flow:
            html += Markup('<h4 class="o_sd_title">%s</h4>') % _("Re-allocation Flow")
            html += Markup(
                '<div class="o_sd_scroll"><table class="o_sd_table o_sd_flow"><thead><tr>'
                '<th>%s</th><th></th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>'
            ) % (_("From Department"), _("To Department"), _("Type"), _("Employees"), _("Amount"))
            type_labels = dict(self.env["salary.distribution.line"]._fields["dist_type"].selection)
            for (source, target, dist_type), data in flow:
                html += Markup(
                    '<tr><td>%s</td><td class="o_sd_arrow"><i class="fa fa-long-arrow-right"></i></td><td>%s</td>'
                    '<td><span class="o_sd_badge o_sd_badge_%s">%s</span></td><td>%s</td><td>%s</td></tr>'
                ) % (
                    self._department_label(source), self._department_label(target), dist_type,
                    type_labels[dist_type], len(data["employees"]), self._fmt(data["amount"], False),
                )
            html += Markup("</tbody></table></div>")
        html += Markup("</div>")
        return html

    def _render_journal_html(self):
        self.ensure_one()
        html = Markup('<div class="o_sd_report">')
        by_rule = defaultdict(lambda: self.env["salary.distribution.journal"])
        for line in self.journal_line_ids:
            by_rule[line.salary_rule_id] |= line
        type_labels = dict(self.env["salary.distribution.journal"]._fields["dist_type"].selection)
        for index, (rule, lines) in enumerate(by_rule.items(), start=1):
            debit, credit = sum(lines.mapped("debit")), sum(lines.mapped("credit"))
            balanced = self.currency_id.is_zero(debit - credit)
            dist_type = lines[0].dist_type
            html += Markup(
                '<div class="o_sd_entry"><div class="o_sd_entry_head o_sd_entry_%s">'
                '<span class="o_sd_entry_no">%s</span><span class="o_sd_entry_name">%s</span>'
                '<span class="o_sd_badge o_sd_badge_%s">%s</span>'
                '<span class="o_sd_entry_remark">%s</span>'
                '<span class="o_sd_entry_status %s"><i class="fa %s"></i> %s</span></div>'
            ) % (
                dist_type, index, rule.name, dist_type, type_labels.get(dist_type, ""), lines[0].remarks,
                "o_sd_ok" if balanced else "o_sd_ko",
                "fa-check-circle" if balanced else "fa-exclamation-triangle",
                _("Balanced") if balanced else _("Not Balanced"),
            )
            html += Markup(
                '<div class="o_sd_scroll"><table class="o_sd_table o_sd_journal"><thead><tr>'
                '<th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>'
            ) % (_("G/L Code"), _("G/L Name"), _("Project"), _("SBU"), _("Debit"), _("Credit"))
            for line in lines:
                html += Markup(
                    '<tr class="%s"><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                ) % (
                    "o_sd_payable" if line.is_payable else "",
                    line.gl_code or "", line.gl_name or "", line.project_code or "", line.sbu_code or "",
                    self._fmt(line.debit), self._fmt(line.credit),
                )
            html += Markup(
                '</tbody><tfoot><tr><td colspan="4">%s</td><td>%s</td><td>%s</td></tr></tfoot></table></div></div>'
            ) % (_("Total"), self._fmt(debit, False), self._fmt(credit, False))
        html += Markup("</div>")
        return html

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    def _generate_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        title = workbook.add_format({"bold": True, "font_size": 14})
        head = workbook.add_format({"bold": True, "bg_color": "#714B67", "font_color": "#FFFFFF", "border": 1})
        section = workbook.add_format({"bold": True, "bg_color": "#EDE7EC", "border": 1})
        text = workbook.add_format({"border": 1})
        money = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        money_bold = workbook.add_format({"num_format": "#,##0.00", "border": 1, "bold": True, "bg_color": "#F3F3F3"})
        bold = workbook.add_format({"bold": True, "border": 1, "bg_color": "#F3F3F3"})

        # Journal entries, laid out like the accounting salary sheet
        sheet = workbook.add_worksheet(_("Journal Entries"))
        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 1, 36)
        sheet.set_column(2, 3, 16)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 6, 12)
        sheet.write(0, 0, "%s (%s - %s)" % (self.name, self.date_start or "", self.date_end or ""), title)
        row = 2
        by_rule = defaultdict(lambda: self.env["salary.distribution.journal"])
        for line in self.journal_line_ids:
            by_rule[line.salary_rule_id] |= line
        for index, (rule, lines) in enumerate(by_rule.items(), start=1):
            sheet.merge_range(row, 0, row, 6, "%s. %s" % (index, rule.name), section)
            row += 1
            for col, label in enumerate([_("G/L Acct Code"), _("G/L Acct Name"), _("Debit"), _("Credit"),
                                         _("Remarks"), _("Project"), _("SBU")]):
                sheet.write(row, col, label, head)
            row += 1
            for line in lines:
                sheet.write(row, 0, line.gl_code or "", text)
                sheet.write(row, 1, line.gl_name or "", text)
                for col, amount in ((2, line.debit), (3, line.credit)):
                    if amount:
                        sheet.write_number(row, col, amount, money)
                    else:
                        sheet.write(row, col, "", text)
                sheet.write(row, 4, line.remarks or "", text)
                sheet.write(row, 5, line.project_code or "", text)
                sheet.write(row, 6, line.sbu_code or "", text)
                row += 1
            sheet.write(row, 1, _("Total"), bold)
            sheet.write_number(row, 2, sum(lines.mapped("debit")), money_bold)
            sheet.write_number(row, 3, sum(lines.mapped("credit")), money_bold)
            row += 2

        # Rule x department matrix
        sheet = workbook.add_worksheet(_("Summary"))
        departments = self._get_departments()
        sheet.set_column(0, 0, 32)
        sheet.set_column(1, len(departments) + 1, 16)
        sheet.write(0, 0, _("Salary Rules by Department"), title)
        sheet.write(2, 0, _("Salary Rule"), head)
        for col, department in enumerate(departments, start=1):
            sheet.write(2, col, self._department_label(department), head)
        sheet.write(2, len(departments) + 1, _("Total"), head)
        row = 3
        for dist_type, label in (("earning", _("Earnings")), ("deduction", _("Deductions"))):
            section_rows = [(r, a) for r, t, a in self._get_rule_department_amounts() if t == dist_type]
            if not section_rows:
                continue
            sheet.merge_range(row, 0, row, len(departments) + 1, label, section)
            row += 1
            for rule, amounts in section_rows:
                sheet.write(row, 0, rule.name, text)
                for col, department in enumerate(departments, start=1):
                    sheet.write_number(row, col, amounts.get(department, 0.0), money)
                sheet.write_number(row, len(departments) + 1, sum(amounts.values()), money_bold)
                row += 1
            row += 1

        # Employee details
        sheet = workbook.add_worksheet(_("Details"))
        headers = [_("Employee"), _("Employee Department"), _("Charged Department"), _("Salary Rule"),
                   _("Type"), _("Share (%)"), _("Amount")]
        sheet.set_column(0, 4, 26)
        sheet.set_column(5, 6, 16)
        for col, label in enumerate(headers):
            sheet.write(0, col, label, head)
        type_labels = dict(self.env["salary.distribution.line"]._fields["dist_type"].selection)
        for row, line in enumerate(self.line_ids.sorted(lambda l: (l.employee_id.name or "", l.rule_sequence)), start=1):
            sheet.write(row, 0, line.employee_id.name, text)
            sheet.write(row, 1, self._department_label(line.home_department_id), text)
            sheet.write(row, 2, self._department_label(line.department_id), text)
            sheet.write(row, 3, line.salary_rule_id.name, text)
            sheet.write(row, 4, type_labels[line.dist_type], text)
            sheet.write_number(row, 5, line.percentage, money)
            sheet.write_number(row, 6, line.amount, money)

        workbook.close()
        return output.getvalue()
