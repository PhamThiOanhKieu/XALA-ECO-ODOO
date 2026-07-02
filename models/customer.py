from odoo import models, fields, api

class XalaEcoCustomer(models.Model):
    _name = 'xalaeco.customer'
    _description = 'Khách hàng XALA ECO'

    # --- THÔNG TIN ĐỊNH DANH ---
    name = fields.Char(string='Tên khách hàng', required=True)
    customer_code = fields.Char(string='Mã khách hàng', required=True)
    phone = fields.Char(string='Số điện thoại')
    email = fields.Char(string='Email')
    area = fields.Selection([
        ('Tuyến Thủ Đức', 'Tuyến Thủ Đức'),
        ('Tuyến Bình Thạnh', 'Tuyến Bình Thạnh'),
        ('Tuyến Huỳnh Tịnh Của - Trần Quốc Toản', 'Tuyến Huỳnh Tịnh Của - Trần Quốc Toản'),
        ('Tuyến Phan Xích Long - Nguyễn Kiệm', 'Tuyến Phan Xích Long - Nguyễn Kiệm'),
        ('Tuyến Tân Bình - Tân Phú', 'Tuyến Tân Bình - Tân Phú'),
        ('Tuyến Quận 7 - Nhà Bè', 'Tuyến Quận 7 - Nhà Bè'),
        ('Tuyến Quận 8 - Bình Chánh', 'Tuyến Quận 8 - Bình Chánh'),
        ('Tuyến Hóc Môn - Quận 12', 'Tuyến Hóc Môn - Quận 12'),
        ('Tuyến Nguyễn Trãi - Trần Hưng Đạo', 'Tuyến Nguyễn Trãi - Trần Hưng Đạo'),
    ], string='Khu vực/Tuyến')
    route_id = fields.Char(string='Mã Tuyến')
    

    # --- ĐỊA CHỈ PHỤC VỤ ---
   
    district = fields.Selection([
        ('urban', 'TP. Thủ Đức/Bình Thạnh/Quận 1/Quận 3/Quận 5/Quận 10/Quận 6/Quận 7/QuậnBình Tân/Tân Phú/Phú Nhuận/'),
        ('suburban', 'Hóc Môn/Nhà Bè/Cần Giờ'),
    ], string="Khu vực/Quận huyện")
    

    # --- PHÂN LOẠI & TRẠNG THÁI ---
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

    contract_count = fields.Integer(string='Số hợp đồng', compute='_compute_contract_count')
    state_display = fields.Selection([
        ('active', 'Đang hoạt động'),
        ('near_expired', 'Sắp hết hạn'),
        ('expired', 'Đã hết hạn'),
        ('paused', 'Tạm ngưng'),
        ('stopped', 'Ngừng dịch vụ'),
    ], string='Trạng thái hoạt động', compute='_compute_state_display')

    # --- THÔNG TIN HÓA ĐƠN (ĐỒNG BỘ ĐẦY ĐỦ VỚI XML VÀ CONTRACT) ---
    need_invoice = fields.Boolean(string='Có nhu cầu xuất hóa đơn', default=False)
    tax_code = fields.Char(string='Mã số thuế')
    invoice_name = fields.Char(string='Tên đơn vị xuất hóa đơn')
    invoice_address = fields.Text(string='Địa chỉ xuất hóa đơn')
    
    note = fields.Text(string='Ghi chú')

    # --- MỐI QUAN HỆ VỚI HỢP ĐỒNG ---
    contract_ids = fields.One2many(
        'xalaeco.contract',
        'customer_id',
        string='Hợp đồng'
    )

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for record in self:
            record.contract_count = len(record.contract_ids)

    @api.depends('state', 'contract_ids.state')
    def _compute_state_display(self):
        for record in self:
            if record.state == 'paused':
                record.state_display = 'paused'
            elif record.state == 'stopped':
                record.state_display = 'stopped'
            else:
                contracts = record.contract_ids
                if not contracts:
                    record.state_display = 'active'
                else:
                    contract_states = contracts.mapped('state')
                    if 'near_expired' in contract_states:
                        record.state_display = 'near_expired'
                    elif 'active' in contract_states:
                        record.state_display = 'active'
                    elif 'expired' in contract_states:
                        record.state_display = 'expired'
                    else:
                        record.state_display = 'active'

    # --- CHỨC NĂNG TẠO NHANH HỢP ĐỒNG TỪ KHÁCH HÀNG ---
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
                'default_invoice_required': self.need_invoice,
                'default_tax_code': self.tax_code,
                'default_invoice_name': self.invoice_name,
                'default_invoice_address': self.invoice_address,
            }
        }