from odoo import models, fields

class XalaEcoDashboard(models.Model):
    _name = 'xalaeco.dashboard'
    _description = 'Dashboard XALA ECO'

    name = fields.Char(string='Tên', default='Tổng quan XALA ECO')

    total_customers = fields.Integer(string='Tổng khách hàng', compute='_compute_dashboard')
    active_contracts = fields.Integer(string='Hợp đồng hiệu lực', compute='_compute_dashboard')
    near_expired_contracts = fields.Integer(string='Hợp đồng sắp hết hạn', compute='_compute_dashboard')
    total_revenue = fields.Float(string='Doanh thu đã thu', compute='_compute_dashboard')
    total_expected = fields.Float(string='Tổng phải thu', compute='_compute_dashboard')
    total_debt = fields.Float(string='Tổng còn nợ', compute='_compute_dashboard')

    def _compute_dashboard(self):
        Customer = self.env['xalaeco.customer']
        Contract = self.env['xalaeco.contract']
        Payment = self.env['xalaeco.payment']

        for record in self:
            payments = Payment.search([])
            record.total_customers = Customer.search_count([])
            record.active_contracts = Contract.search_count([('state', 'in', ['active', 'near_expired'])])
            record.near_expired_contracts = Contract.search_count([('state', '=', 'near_expired')])
            record.total_revenue = sum(payments.mapped('amount_paid'))
            record.total_expected = sum(payments.mapped('amount_due'))
            record.total_debt = sum(payments.mapped('debt_amount'))