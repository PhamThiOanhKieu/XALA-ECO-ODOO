from odoo import models, fields, api, _
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

class XalaEcoContract(models.Model):
    _name = 'xalaeco.contract'
    _description = 'Hợp đồng dịch vụ XALA ECO'
    _order = 'priority_order asc, end_date asc'

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
    
    waste_volume = fields.Float(string='Khối lượng rác (kg/tháng)')

    collection_fee = fields.Float(string='Phí thu gom', compute='_compute_service_fee', store=True, readonly=False)
    transport_fee = fields.Float(string='Phí vận chuyển', compute='_compute_service_fee', store=True, readonly=False)
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

    is_near_expired = fields.Boolean(string='Sắp hết hạn (7 ngày)', compute='_compute_near_expired')
    days_until_expiry = fields.Integer(string='Số ngày còn lại', compute='_compute_near_expired')

    customer_phone = fields.Char(related='customer_id.phone', string='SĐT Khách hàng', readonly=True)
    customer_email = fields.Char(related='customer_id.email', string='Email Khách hàng', readonly=True)
    expiry_status_msg = fields.Char(string='Cảnh báo hạn', compute='_compute_expiry_status_msg')
    priority_order = fields.Integer(string='Thứ tự ưu tiên', compute='_compute_priority_order', store=True)

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id and self.customer_id.district:
            if self.customer_id.district in ['binh_chanh', 'can_gio', 'cu_chi', 'hoc_mon', 'nha_be', 'suburban']:
                self.pricing_area = 'suburban'
            else:
                self.pricing_area = 'urban'

    # Bảng giá: mỗi mốc khối lượng ứng với (phí thu gom, phí vận chuyển).
    # Trên 420kg: đơn giá theo kg cho từng loại phí.
    _FEE_TABLE = {
        'urban': {
            'tiers': [(126, 61000, 23000), (250, 91000, 34000), (420, 163000, 60000)],
            'rate_per_kg': (485.97, 180.07),
        },
        'suburban': {
            'tiers': [(126, 57000, 23000), (250, 85000, 34000), (420, 152000, 60000)],
            'rate_per_kg': (485.97, 180.07),
        },
    }

    @api.depends('pricing_area', 'waste_volume')
    def _compute_service_fee(self):
        for record in self:
            kg = record.waste_volume or 0
            table = self._FEE_TABLE.get(record.pricing_area)
            if not table:
                record.collection_fee = 0.0
                record.transport_fee = 0.0
                record.service_fee = 0.0
                continue

            collection = transport = None
            for limit, coll, trans in table['tiers']:
                if kg <= limit:
                    collection, transport = coll, trans
                    break
            if collection is None:
                coll_rate, trans_rate = table['rate_per_kg']
                collection = kg * coll_rate
                transport = kg * trans_rate

            record.collection_fee = collection
            record.transport_fee = transport
            record.service_fee = collection + transport

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.contract') or 'New'
        records = super(XalaEcoContract, self).create(vals_list)
        records._update_state_from_dates()
        return records

    @api.depends('end_date', 'state')
    def _compute_near_expired(self):
        today = date.today()
        for record in self:
            if record.end_date:
                delta = (record.end_date - today).days
                record.days_until_expiry = delta
                record.is_near_expired = (0 <= delta <= 7) and (record.state in ['active', 'near_expired'])
            else:
                record.days_until_expiry = -1
                record.is_near_expired = False

    @api.depends('end_date', 'state')
    def _compute_expiry_status_msg(self):
        today = date.today()
        for record in self:
            if record.state == 'draft':
                record.expiry_status_msg = 'Nháp'
            elif record.state == 'cancelled':
                record.expiry_status_msg = 'Đã hủy'
            elif record.state == 'expired' or (record.end_date and record.end_date < today):
                record.expiry_status_msg = 'Đã hết hạn'
            elif record.end_date:
                delta = (record.end_date - today).days
                if delta == 0:
                    record.expiry_status_msg = 'Hết hạn hôm nay'
                else:
                    record.expiry_status_msg = f'Còn {delta} ngày'
            else:
                record.expiry_status_msg = 'Vô thời hạn'

    @api.depends('state')
    def _compute_priority_order(self):
        for record in self:
            if record.state == 'near_expired':
                record.priority_order = 1
            elif record.state == 'expired':
                record.priority_order = 2
            elif record.state == 'active':
                record.priority_order = 3
            elif record.state == 'draft':
                record.priority_order = 4
            else:
                record.priority_order = 5

    def _update_state_from_dates(self):
        today = date.today()
        for record in self:
            if record.state in ['active', 'near_expired', 'expired']:
                if record.end_date:
                    if record.end_date < today:
                        record.state = 'expired'
                    elif record.end_date <= today + timedelta(days=7):
                        record.state = 'near_expired'
                    else:
                        record.state = 'active'
                else:
                    record.state = 'active'

    @api.constrains('state', 'start_date', 'end_date')
    def _check_state_dates(self):
        """Đã gỡ bỏ logic ValidationError cũ để tránh chặn người dùng khi chỉnh ngày về quá khứ"""
        pass

    def write(self, vals):
        # Tính toán lại trạng thái tự động dựa trên ngày kết thúc mới TRƯỚC KHI lưu vào DB
        if 'end_date' in vals:
            today = date.today()
            end_date_val = fields.Date.to_date(vals['end_date'])
            
            for record in self:
                # Chỉ tự động cập nhật trạng thái nếu hợp đồng đang ở nhóm quản lý vòng đời (Active, Near Expired, Expired)
                current_state = vals.get('state', record.state)
                if current_state in ['active', 'near_expired', 'expired']:
                    if end_date_val:
                        if end_date_val < today:
                            vals['state'] = 'expired'
                        elif end_date_val <= today + timedelta(days=7):
                            vals['state'] = 'near_expired'
                        else:
                            vals['state'] = 'active'
                    else:
                        vals['state'] = 'active'

        res = super(XalaEcoContract, self).write(vals)
        if 'end_date' in vals or 'start_date' in vals:
            self._update_state_from_dates()
        return res

    def action_active_contract(self):
        """Kích hoạt hợp đồng."""
        for record in self:
            today = date.today()
            correct_state = 'active'
            if record.end_date:
                if record.end_date < today:
                    correct_state = 'expired'
                elif record.end_date <= today + timedelta(days=7):
                    correct_state = 'near_expired'
            record.write({'state': correct_state})

    @api.model
    def _cron_check_contract_expiry(self):
        """Cron job chạy hàng ngày để kiểm tra hợp đồng sắp hết hạn và đã hết hạn."""
        today = date.today()
        warning_date = today + timedelta(days=7)

        # Tìm hợp đồng đang hiệu lực sắp hết hạn trong 7 ngày
        near_expired_contracts = self.search([
            ('state', '=', 'active'),
            ('end_date', '!=', False),
            ('end_date', '<=', warning_date),
            ('end_date', '>=', today),
        ])
        if near_expired_contracts:
            internal_users = self.env['res.users'].search([('share', '=', False)])
            partner_ids = internal_users.mapped('partner_id').ids

            for contract in near_expired_contracts:
                contract.state = 'near_expired'
                days_left = (contract.end_date - today).days
                _logger.info('Hợp đồng %s sắp hết hạn sau %d ngày.', contract.name, days_left)
                pass

        # Tìm hợp đồng đã hết hạn
        expired_contracts = self.search([
            ('state', 'in', ['active', 'near_expired']),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])
        for contract in expired_contracts:
            contract.state = 'expired'
            _logger.info('Hợp đồng %s đã hết hạn.', contract.name)

    def action_renew_contract(self):
        """Gia hạn hợp đồng thêm 1 năm từ ngày kết thúc hiện tại."""
        for record in self:
            if record.end_date:
                record.write({
                    'start_date': record.end_date,
                    'end_date': record.end_date + timedelta(days=365),
                    'state': 'active',
                })

    def action_rollover_contract(self):
        """Đáo hạn hợp đồng - tạo hợp đồng mới từ ngày hôm nay."""
        today = date.today()
        for record in self:
            record.write({
                'start_date': today,
                'end_date': today + timedelta(days=365),
                'state': 'active',
            })