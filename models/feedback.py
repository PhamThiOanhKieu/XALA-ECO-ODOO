from odoo import models, fields, api
from datetime import timedelta

class XalaecoFeedback(models.Model):
    _name = 'xalaeco.feedback'
    _description = 'Quản lý khiếu nại'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã Phản Hồi', required=True, copy=False, default='Mới')
    
    # 1. BỎ thuộc tính required=True ở đây để Odoo không chặn lúc Import
    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', tracking=True)
    
    # 2. THÊM TRƯỜNG TRUNG GIAN ĐỂ HỨNG SĐT TỪ EXCEL
    # store=False nghĩa là trường này chỉ dùng tạm lúc import, không phình to database
    import_phone = fields.Char(string='Số điện thoại (Dùng để Import)', store=False) 

    route_id = fields.Char(string='Mã Tuyến', related='customer_id.route_id', store=True)
    area = fields.Selection(related='customer_id.area', string='Khu vực/Tuyến', store=True)

    feedback_type = fields.Selection([
        ('late', 'Chậm thu gom'),
        ('messy', 'Làm rơi vãi rác'),
        ('attitude', 'Thái độ nhân viên'),
        ('other', 'Khác')
    ], string='Phân loại lỗi', required=True, tracking=True)

    content = fields.Text(string='Nội dung chi tiết', required=True)
    evidence_image = fields.Image(string='Ảnh phản ánh đính kèm', max_width=1024, max_height=1024)
    resolution_image = fields.Image(string='Ảnh kết quả (Nhân viên chụp)', max_width=1024, max_height=1024)

    state = fields.Selection([
        ('draft', 'Đã gửi khiếu nại'),
        ('received', 'Đã tiếp nhận'),
        ('processed', 'Đã xử lý'),
        ('closed', 'Hoàn thành')
    ], string='Trạng thái', default='draft', tracking=True)

    assigned_employee_id = fields.Many2one('xala.employee', string='Nhân viên xử lý', tracking=True)
    result_image = fields.Image(string='Ảnh kết quả xử lý', max_width=1024, max_height=1024)
    resolution_note = fields.Text(string='Ghi chú của nhân viên')

    customer_rating = fields.Selection([
        ('satisfied', 'Hài lòng'),
        ('unsatisfied', 'Chưa hài lòng')
    ], string='Đánh giá của khách', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        # 1. XỬ LÝ DỮ LIỆU TRƯỚC KHI LƯU (Cấp mã trên web & Map SĐT từ file)
        for vals in vals_list:
            if vals.get('name', 'Mới') == 'Mới':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.feedback') or 'Mới'

            # Logic tìm khách hàng bằng Số điện thoại (khi Import)
            if not vals.get('customer_id') and vals.get('import_phone'):
                phone_to_find = str(vals['import_phone']).strip()
                customer = self.env['xalaeco.customer'].search([('phone', '=', phone_to_find)], limit=1)
                
                if customer:
                    vals['customer_id'] = customer.id
                else:
                    from odoo.exceptions import ValidationError
                    raise ValidationError(f"Lỗi Import: Không tìm thấy khách hàng nào có số điện thoại {phone_to_find}")

            if not vals.get('customer_id') and not vals.get('import_phone'):
                from odoo.exceptions import ValidationError
                raise ValidationError("Hệ thống yêu cầu: Vui lòng chọn Khách hàng!")

        # 2. TIẾN HÀNH LƯU DỮ LIỆU VÀO DATABASE
        records = super().create(vals_list)

        # 3. AUTO-UPDATE SEQUENCE (Xử lý lỗi nhảy sai mã sau khi Import)
        # Tìm bộ đếm (sequence) của khiếu nại
        seq = self.env['ir.sequence'].search([('code', '=', 'xalaeco.feedback')], limit=1)
        if seq:
            max_imported_num = 0
            for rec in records:
                # Kiểm tra nếu tên có chữ FB (Ví dụ: FB00100)
                if rec.name and rec.name.startswith('FB'):
                    try:
                        # Bỏ chữ 'FB', biến '00100' thành số nguyên 100
                        num = int(rec.name.replace('FB', ''))
                        if num > max_imported_num:
                            max_imported_num = num
                    except ValueError:
                        pass
            
            # Nếu số lớn nhất trong file Import lấn át luôn số hiện tại của hệ thống
            if max_imported_num > 0 and max_imported_num >= seq.number_next_actual:
                # Dùng sudo() để vượt quyền, ép bộ đếm tự động nhảy lên số tiếp theo (Ví dụ 100 + 1 = 101)
                seq.sudo().write({'number_next_actual': max_imported_num + 1})

        return records

    # --- CÁC HÀM CHUYỂN TRẠNG THÁI ---
    def action_accept(self):
        for rec in self:
            rec.state = 'received'

    def action_close(self):
        for rec in self:
            rec.state = 'closed'

    def action_reject(self):
        # Đóng ticket nếu là spam
        for rec in self:
            rec.state = 'closed'
            rec.resolution_note = 'Quản lý từ chối: Khiếu nại không hợp lệ.'

    # --- HÀM TỰ ĐỘNG ĐÓNG SAU 24H (Cron Job) ---
    @api.model
    def _cron_auto_close_feedback(self):
        # Lấy thời điểm 24h trước so với hiện tại
        limit_date = fields.Datetime.now() - timedelta(hours=24)
        # Tìm các ticket 'Đã xử lý' và update_date (write_date) <= 24h trước
        stuck_feedbacks = self.search([
            ('state', '=', 'processed'),
            ('write_date', '<=', limit_date)
        ])
        for fb in stuck_feedbacks:
            fb.write({
                'state': 'closed',
                'resolution_note': 'Hệ thống tự động đóng do khách hàng không phản hồi sau 24h.'
            })
