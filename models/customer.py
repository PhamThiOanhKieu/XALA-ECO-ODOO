'''from odoo import models, fields

class XalaEcoCustomer(models.Model):
    _name = 'xalaeco.customer'
    _description = 'Khách hàng XALA ECO'

    name = fields.Char(string='Tên khách hàng', required=True)
    customer_code = fields.Char(string='Mã khách hàng', required=True)
    phone = fields.Char(string='Số điện thoại')
    address = fields.Text(string='Địa chỉ')
    area = fields.Char(string='Khu vực/Tuyến')

    customer_type = fields.Selection([
        ('household', 'Hộ dân'),
        ('business', 'Hộ kinh doanh'),
        ('restaurant', 'Quán ăn'),
        ('office', 'Văn phòng'),
    ], string='Loại khách hàng', default='household')

    monthly_fee = fields.Float(string='Mức phí tháng', default=87000)
    state = fields.Selection([
        ('active', 'Đang sử dụng'),
        ('paused', 'Tạm ngưng'),
        ('stopped', 'Ngừng dịch vụ'),
    ], string='Trạng thái', default='active')
    
    need_invoice = fields.Boolean(string='Có nhu cầu xuất hóa đơn')

    contract_ids = fields.One2many(
    'xalaeco.contract',
    'customer_id',
    string='Hợp đồng'
    )
    
    def action_create_contract(self):
        self.ensure_one()
        return {
        'type': 'ir.actions.act_window',
        'name': 'Tạo hợp đồng',
        'res_model': 'xalaeco.contract',
        'view_mode': 'form',
        'target': 'current',
        'context': {
            'default_customer_id': self.id,
            'default_service_fee': self.monthly_fee,
            'default_state': 'draft',
            }
        }

    note = fields.Text(string='Ghi chú')'''

from odoo import models, fields


class XalaEcoCustomer(models.Model):
    _name = 'xalaeco.customer'
    _description = 'Khách hàng XALA ECO'

    name = fields.Char(string='Tên khách hàng', required=True)
    customer_code = fields.Char(string='Mã khách hàng', required=True)
    phone = fields.Char(string='Số điện thoại')
    address = fields.Text(string='Địa chỉ')
    area = fields.Char(string='Khu vực/Tuyến')

    customer_type = fields.Selection([
        ('household', 'Hộ dân'),
        ('business', 'Hộ kinh doanh'),
        ('restaurant', 'Quán ăn'),
        ('office', 'Văn phòng'),
    ], string='Loại khách hàng', default='household')

    monthly_fee = fields.Float(string='Phí hộ dân/tháng', default=87000)

    state = fields.Selection([
        ('active', 'Đang sử dụng'),
        ('paused', 'Tạm ngưng'),
        ('stopped', 'Ngừng dịch vụ'),
    ], string='Trạng thái', default='active')

    need_invoice = fields.Boolean(string='Có nhu cầu xuất hóa đơn')
    note = fields.Text(string='Ghi chú')

    contract_ids = fields.One2many(
        'xalaeco.contract',
        'customer_id',
        string='Hợp đồng'
    )

    def action_create_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo hợp đồng xuất hóa đơn',
            'res_model': 'xalaeco.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_customer_id': self.id,
                'default_state': 'draft',
            }
        }