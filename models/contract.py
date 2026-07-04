from odoo import models, fields, api
from datetime import date, timedelta

class XalaEcoContract(models.Model):
    _name = 'xalaeco.contract'
    _description = 'Hợp đồng dịch vụ XALA ECO'

    name = fields.Char(string='Mã hợp đồng', required=True, copy=False, default='New')
    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', required=True)

    service_type = fields.Selection([
        ('household_waste', 'Thu gom rác hộ dân'),
        ('business_waste', 'Thu gom rác hộ kinh doanh'),
        ('restaurant_waste', 'Thu gom rác quán ăn'),
        ('office_waste', 'Thu gom rác văn phòng'),
    ], string='Loại dịch vụ', required=True)

    sign_date = fields.Date(string='Ngày ký')
    start_date = fields.Date(string='Ngày bắt đầu')
    end_date = fields.Date(string='Ngày kết thúc')

    invoice_required = fields.Boolean(string='Có xuất hóa đơn', default=True)
    tax_code = fields.Char(string='Mã số thuế')
    invoice_name = fields.Char(string='Tên đơn vị xuất hóa đơn')
    invoice_address = fields.Text(string='Địa chỉ xuất hóa đơn')

    billing_cycle = fields.Selection([
        ('monthly', 'Theo tháng'),
        ('quarterly', 'Theo quý'),
    ], string='Chu kỳ thu phí', default='monthly')

    pricing_area = fields.Selection([
    ('urban', 'TP Thủ Đức & Các Quận'),
    ('suburban', 'Hóc Môn/Nhà Bè/Cần Giờ'),
    ], string='Khu vực tính giá', default='urban')
    
    waste_volume = fields.Float(string='Khối lượng rác/tháng (kg)')
    
    service_fee = fields.Float( string='Phí phục vụ mỗi kỳ', compute='_compute_service_fee', store=True, readonly=False )

    attachment = fields.Binary(string='File scan hợp đồng')
    attachment_name = fields.Char(string='Tên file')

    legal_note = fields.Text(string='Ghi chú pháp lý')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('active', 'Đang hiệu lực'),
        ('near_expired', 'Sắp hết hạn'),
        ('expired', 'Hết hạn'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft')

    is_near_expired = fields.Boolean(string='Sắp hết hạn 15 ngày', compute='_compute_near_expired')

    @api.depends('pricing_area', 'waste_volume')
    def _compute_service_fee(self):
        for record in self:
            kg = record.waste_volume or 0

        if record.pricing_area == 'urban':
            if kg <= 126:
                record.service_fee = 61000
            elif kg <= 250:
                record.service_fee = 91000
            elif kg <= 420:
                record.service_fee = 163000
            else:
                record.service_fee = kg * 485.97

        elif record.pricing_area == 'suburban':
            if kg <= 126:
                record.service_fee = 57000
            elif kg <= 250:
                record.service_fee = 85000
            elif kg <= 420:
                record.service_fee = 152000
            else:
                record.service_fee = kg * 485.97

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.contract') or 'New'
        return super().create(vals_list)

    def _compute_near_expired(self):
        today = date.today()
        for record in self:
            record.is_near_expired = bool(record.end_date and today <= record.end_date <= today + timedelta(days=15))