from odoo import models, fields, api
from datetime import timedelta

class XalaecoFeedback(models.Model):
    _name = 'xalaeco.feedback'
    _description = 'Quản lý khiếu nại'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # Hỗ trợ log chat bên dưới

    name = fields.Char(string='Mã Phản Hồi', required=True, copy=False, default='Mới')
    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', required=True, tracking=True)
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
        for vals in vals_list:
            if vals.get('name', 'Mới') == 'Mới':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.feedback') or 'Mới'
        return super().create(vals_list)

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