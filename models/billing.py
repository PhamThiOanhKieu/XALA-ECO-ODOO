'''
from odoo import models, fields, api
from odoo.exceptions import UserError


class XalaEcoBilling(models.Model):
    _name = 'xalaeco.billing'
    _description = 'Kỳ thu phí XALA ECO'

    name = fields.Char(string='Tên kỳ thu phí', required=True)
    month = fields.Selection([
        ('01', 'Tháng 01'), ('02', 'Tháng 02'), ('03', 'Tháng 03'),
        ('04', 'Tháng 04'), ('05', 'Tháng 05'), ('06', 'Tháng 06'),
        ('07', 'Tháng 07'), ('08', 'Tháng 08'), ('09', 'Tháng 09'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string='Tháng', required=True)

    year = fields.Selection([
    ('2025', '2025'),
    ('2026', '2026'),
    ('2027', '2027'),
    ('2028', '2028'),('2029', '2029'), ('2030', '2030'),], string='Năm', default='2026', required=True)

    payment_ids = fields.One2many(
        'xalaeco.payment',
        'billing_id',
        string='Danh sách thanh toán'
    )

    customer_count = fields.Integer(string='Tổng khách cần thu', compute='_compute_totals')
    total_expected = fields.Float(string='Tổng phải thu', compute='_compute_totals')
    total_paid = fields.Float(string='Tổng đã thu', compute='_compute_totals')
    total_debt = fields.Float(string='Tổng còn nợ', compute='_compute_totals')

    state = fields.Selection([
        ('draft', 'Mới tạo'),
        ('collecting', 'Đang thu'),
        ('closed', 'Đã chốt kỳ'),
    ], string='Trạng thái', default='draft')

    @api.depends('payment_ids.amount_due', 'payment_ids.amount_paid', 'payment_ids.debt_amount')
    def _compute_totals(self):
        for record in self:
            record.customer_count = len(record.payment_ids)
            record.total_expected = sum(record.payment_ids.mapped('amount_due'))
            record.total_paid = sum(record.payment_ids.mapped('amount_paid'))
            record.total_debt = sum(record.payment_ids.mapped('debt_amount'))

    def action_generate_payments(self):
        for billing in self:
        # 1. Sinh công nợ cho hộ dân: không cần hợp đồng
             households = self.env['xalaeco.customer'].search([
            ('customer_type', '=', 'household'),
            ('state', '=', 'active')
        ])

        for customer in households:
            existed = self.env['xalaeco.payment'].search([
                ('billing_id', '=', billing.id),
                ('customer_id', '=', customer.id),
                ('contract_id', '=', False),
            ], limit=1)

            if not existed:
                self.env['xalaeco.payment'].create({
                    'customer_id': customer.id,
                    'billing_id': billing.id,
                    'amount_due': customer.monthly_fee,
                    'amount_paid': 0,
                    'payment_method': 'bank',
                })

        # 2. Sinh công nợ cho hộ kinh doanh/quán ăn/văn phòng: dựa vào hợp đồng hiệu lực
        contracts = self.env['xalaeco.contract'].search([
            ('state', '=', 'active')
        ])

        for contract in contracts:
            if contract.customer_id.customer_type == 'household':
                continue

            existed = self.env['xalaeco.payment'].search([
                ('billing_id', '=', billing.id),
                ('contract_id', '=', contract.id),
            ], limit=1)

            if not existed:
                self.env['xalaeco.payment'].create({
                    'customer_id': contract.customer_id.id,
                    'contract_id': contract.id,
                    'billing_id': billing.id,
                    'amount_due': contract.service_fee,
                    'amount_paid': 0,
                    'payment_method': 'bank',
                })

        billing.state = 'collecting'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Thanh toán QR của kỳ thu phí',
            'res_model': 'xalaeco.payment',
            'view_mode': 'list,form',
            'domain': [('billing_id', '=', billing.id)],
            'context': {'default_billing_id': billing.id},
            }

    def action_close_period(self):
        for record in self:
            record.state = 'closed'  
            '''

from odoo import models, fields, api


class XalaEcoBilling(models.Model):
    _name = 'xalaeco.billing'
    _description = 'Kỳ thu phí XALA ECO'

    name = fields.Char(string='Tên kỳ thu phí', required=True)

    month = fields.Selection([
        ('01', 'Tháng 01'), ('02', 'Tháng 02'), ('03', 'Tháng 03'),
        ('04', 'Tháng 04'), ('05', 'Tháng 05'), ('06', 'Tháng 06'),
        ('07', 'Tháng 07'), ('08', 'Tháng 08'), ('09', 'Tháng 09'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string='Tháng', required=True)

    year = fields.Selection([
        ('2025', '2025'),
        ('2026', '2026'),
        ('2027', '2027'),
        ('2028', '2028'),
        ('2029', '2029'),
        ('2030', '2030'),
    ], string='Năm', default='2026', required=True)

    area = fields.Char(string='Tuyến/Khu vực thu phí')

    payment_ids = fields.One2many(
        'xalaeco.payment',
        'billing_id',
        string='Danh sách thanh toán'
    )

    customer_count = fields.Integer(string='Tổng khách cần thu', compute='_compute_totals')
    total_expected = fields.Float(string='Tổng phải thu', compute='_compute_totals')
    total_paid = fields.Float(string='Tổng đã thu', compute='_compute_totals')
    total_debt = fields.Float(string='Tổng còn nợ', compute='_compute_totals')

    state = fields.Selection([
        ('draft', 'Mới tạo'),
        ('collecting', 'Đang thu'),
        ('closed', 'Đã chốt kỳ'),
    ], string='Trạng thái', default='draft')

    @api.depends('payment_ids.amount_due', 'payment_ids.amount_paid', 'payment_ids.debt_amount')
    def _compute_totals(self):
        for record in self:
            record.customer_count = len(record.payment_ids)
            record.total_expected = sum(record.payment_ids.mapped('amount_due'))
            record.total_paid = sum(record.payment_ids.mapped('amount_paid'))
            record.total_debt = sum(record.payment_ids.mapped('debt_amount'))

    def action_generate_payments(self):
        for billing in self:
            domain = [('state', '=', 'active')]
            if billing.area:
                domain.append(('area', '=', billing.area))

            customers = self.env['xalaeco.customer'].search(domain)

            for customer in customers:
                existed = self.env['xalaeco.payment'].search([
                    ('billing_id', '=', billing.id),
                    ('customer_id', '=', customer.id),
                ], limit=1)

                if existed:
                    continue

                contract = self.env['xalaeco.contract'].search([
                    ('customer_id', '=', customer.id),
                    ('state', '=', 'active'),
                ], limit=1)

                amount_due = contract.service_fee if contract else customer.monthly_fee

                self.env['xalaeco.payment'].create({
                    'customer_id': customer.id,
                    'contract_id': contract.id if contract else False,
                    'billing_id': billing.id,
                    'amount_due': amount_due,
                    'amount_paid': 0,
                    'payment_method': 'bank',
                    'note': 'Sinh từ hợp đồng xuất hóa đơn' if contract else 'Sinh từ phí hộ dân/tháng',
                })

            billing.state = 'collecting'

            return {
                'type': 'ir.actions.act_window',
                'name': 'Thanh toán QR của kỳ thu phí',
                'res_model': 'xalaeco.payment',
                'view_mode': 'list,form',
                'domain': [('billing_id', '=', billing.id)],
                'context': {'default_billing_id': billing.id},
            }

    def action_close_period(self):
        for record in self:
            record.state = 'closed'