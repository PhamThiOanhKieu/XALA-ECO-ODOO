from odoo import models, fields, api

class XalaEcoContract(models.Model):
    _inherit = 'xalaeco.contract'

    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', required=False)
    service_type = fields.Selection([
        ('household_waste', 'Thu gom rác hộ dân'),
        ('business_waste', 'Thu gom rác hộ kinh doanh'),
        ('restaurant_waste', 'Thu gom rác quán ăn'),
        ('office_waste', 'Thu gom rác văn phòng'),
    ], string='Loại dịch vụ', required=False)

    # Excel dataset import helper fields
    customer_name = fields.Char(string='customer_name')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('customer_id') and vals.get('customer_name'):
                cust = self.env['xalaeco.customer'].search([('name', '=', vals.get('customer_name'))], limit=1)
                if cust:
                    vals['customer_id'] = cust.id
            if not vals.get('service_type'):
                vals['service_type'] = 'household_waste'
            if not vals.get('name') or vals.get('name') == 'New':
                import random
                vals['name'] = 'HD' + str(random.randint(10000, 99999))
        return super(XalaEcoContract, self).create(vals_list)
