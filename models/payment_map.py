import random
from odoo import models, fields, api

class XalaEcoPayment(models.Model):
    _inherit = 'xalaeco.payment'

    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', required=False)

    # Excel dataset import helper fields
    payment_no = fields.Char(string='payment_no')
    billing_period = fields.Char(string='billing_period')
    customer_code = fields.Char(string='customer_code')
    customer_name = fields.Char(string='customer_name')
    contract_no = fields.Char(string='contract_no')
    route_id = fields.Char(string='route_id')
    route_name = fields.Char(string='route_name')
    payment_status = fields.Char(string='payment_status')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('payment_no') and (not vals.get('name') or vals.get('name') == 'New'):
                vals['name'] = vals['payment_no']
                
            if not vals.get('customer_id'):
                if vals.get('customer_code'):
                    cust = self.env['xalaeco.customer'].search([('customer_code', '=', vals.get('customer_code'))], limit=1)
                    if cust:
                        vals['customer_id'] = cust.id
                if not vals.get('customer_id') and vals.get('customer_name'):
                    cust = self.env['xalaeco.customer'].search([('name', '=', vals.get('customer_name'))], limit=1)
                    if cust:
                        vals['customer_id'] = cust.id
                        
            if not vals.get('contract_id') and vals.get('contract_no'):
                contract = self.env['xalaeco.contract'].search([('name', '=', vals.get('contract_no'))], limit=1)
                if contract:
                    vals['contract_id'] = contract.id
                    
            if not vals.get('billing_id') and vals.get('billing_period'):
                period_name = vals.get('billing_period')
                billing = self.env['xalaeco.billing'].search([('name', '=', period_name)], limit=1)
                if not billing:
                    month = '06'
                    year = '2026'
                    try:
                        if '/' in period_name:
                            parts = period_name.split('/')
                            m_part = parts[0][-2:]
                            y_part = parts[1][:4]
                            if m_part.isdigit() and y_part.isdigit():
                                month = m_part
                                year = y_part
                    except Exception:
                        pass
                    billing = self.env['xalaeco.billing'].create({
                        'name': period_name,
                        'month': month,
                        'year': year,
                        'state': 'collecting'
                    })
                vals['billing_id'] = billing.id
                
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = 'PAY' + str(random.randint(10000, 99999))
                
            if not vals.get('customer_id'):
                cust = self.env['xalaeco.customer'].search([], limit=1)
                if cust:
                    vals['customer_id'] = cust.id
        return super(XalaEcoPayment, self).create(vals_list)
