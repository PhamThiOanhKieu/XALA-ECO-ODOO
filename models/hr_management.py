from odoo import models, fields, api
from odoo.exceptions import ValidationError

# 1. BẢNG QUẢN LÝ NHÂN VIÊN 
class XalaEmployee(models.Model):
    _name = 'xala.employee'
    _description = 'Quản lý Nhân viên Xala Eco'
    _rec_name = 'employee_name'
    _rec_names_search = ['employee_name', 'employee_code']

    @api.depends('employee_code', 'employee_name')
    def _compute_display_name(self):
        for rec in self:
            if rec.employee_code and rec.employee_name:
                rec.display_name = f"[{rec.employee_code}] {rec.employee_name}"
            else:
                rec.display_name = rec.employee_name or rec.employee_code or ''

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            name_domain = ['|', ('employee_code', operator, name), ('employee_name', operator, name)]
            return self._search(name_domain + domain, limit=limit, order=order)
        return super(XalaEmployee, self)._name_search(name, domain=domain, operator=operator, limit=limit, order=order)

    employee_code = fields.Char(string='Mã nhân viên (ID)', required=True)
    employee_name = fields.Char(string='Tên nhân viên', required=True)
    phone = fields.Char(string='Số điện thoại')
    role = fields.Char(string='Vai trò')
    route_id = fields.Char(string='Mã tuyến đường')
    route_name = fields.Char(string='Tên tuyến đường')
    login_account = fields.Char(string='Tài khoản đăng nhập',required=True, placeholder="nv001@xalaeco.local")
    state = fields.Selection([
        ('active','Đang làm việc'),
        ('inactive','Đã nghỉ việc')
    ], string='Trạng thái', default= 'active')
    password = fields.Char(string='Mật khẩu đăng nhập', required=True, default='nhanvien@123', readonly=True)

    # Bổ sung cho tính năng bản đồ giám sát GPS real-time
    current_lat = fields.Float(string='Vĩ độ hiện tại', digits=(16, 6))
    current_lng = fields.Float(string='Kinh độ hiện tại', digits=(16, 6))
    last_gps_update = fields.Datetime(string='Cập nhật GPS lúc')
    location_history = fields.Text(string='Lịch sử di chuyển (JSON)', default='[]')

    def update_gps_location(self, lat, lng):
        self.ensure_one()
        import json
        history_list = []
        if self.location_history:
            try:
                history_list = json.loads(self.location_history)
            except Exception:
                history_list = []
        
        # Append new point with timestamp
        now_str = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Avoid duplicate consecutive coordinates to save space
        if not history_list or abs(history_list[-1][0] - lat) > 0.00001 or abs(history_list[-1][1] - lng) > 0.00001:
            history_list.append([lat, lng, now_str])
            
        # Keep last 150 points for trail rendering
        if len(history_list) > 150:
            history_list = history_list[-150:]
            
        self.write({
            'current_lat': lat,
            'current_lng': lng,
            'last_gps_update': fields.Datetime.now(),
            'location_history': json.dumps(history_list)
        })

# 2. BẢNG PHÂN CÔNG CA LÀM VIỆC 
class XalaShift(models.Model):
    _name = 'xala.shift'
    _description = 'Quản lý phân công ca làm việc'
    shift_code = fields.Char(string='Mã ca làm việc', required=True)

    employee_id = fields.Many2one('xala.employee', string='Nhân viên được phân công', required=True, domain=[('state', '=', 'active')])
    
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã nhân viên', store=True)
    phone = fields.Char(related='employee_id.phone', string='Số điện thoại')
    role = fields.Char(related="employee_id.role", string='Vai trò')
    route_id= fields.Char(string='Mã tuyến đường')
    route_name= fields.Char(string='Tên tuyến đường')
   
    date_assigned = fields.Date(string='Ngày làm việc', default=fields.Date.today, required=True)
    shift_type = fields.Selection([
        ('sang', 'Ca Sáng'),
        ('chieu', 'Ca Chiều')
    ], string='Khung giờ ca', default='sang')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.route_id = self.employee_id.route_id
            self.route_name = self.employee_id.route_name
        else:
            self.route_id = False
            self.route_name = False

    @api.depends('employee_id', 'date_assigned', 'shift_type', 'shift_code')
    def _compute_shift_name(self):
        for rec in self:
            if rec.employee_id and rec.date_assigned:
                rec.name = f"{rec.shift_code} - {rec.employee_id.employee_name} {rec.date_assigned} ({dict(rec._fields['shift_type'].selection).get(rec.shift_type)})"
            else:
                rec.name = "Ca làm việc mới"

    @api.model_create_multi
    def create(self, vals_list):
        shifts = super(XalaShift, self).create(vals_list)
        for shift in shifts:
            self.env['xala.work.history'].create({
                'shift_code': shift.shift_code,
                'work_date': shift.date_assigned,
                'employee_code': shift.employee_code,
                'employee_name': shift.employee_id.employee_name,
                'route_id': shift.route_id,
                'route_name': shift.route_name,
                'shift_status': 'draft'  
            })
        return shifts

# 3. BẢNG LỊCH SỬ CA LÀM VIỆC 
class XalaWorkHistory(models.Model):
    _name = 'xala.work.history'
    _description = 'Lịch sử ca làm việc'
    _rec_name = 'shift_code'

    shift_code = fields.Char(string ='Mã ca')
    work_date = fields.Date(string = 'Ngày làm việc')

    employee_code = fields.Char(string = 'Mã nhân viên')
    employee_name = fields.Char(string = 'Tên nhân viên')
    route_id = fields.Char(string = 'Mã tuyến đường')
    route_name = fields.Char(string = 'Tên tuyến đường')
    start_time = fields.Datetime(string = 'Thời gian Check-in')
    end_time = fields.Datetime(string = 'Thời gian Check-out')
    shift_status = fields.Selection([
        ('draft','Nháp'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Đã hoàn thành'),
        ('absent', 'Vắng mặt'),
        ('cancelled', 'Đã hủy')
    ], string = 'Trạng thái ca', default = 'draft')
    
    gps_check_in = fields.Char(string='GPS Check-in')
    gps_check_out = fields.Char(string='GPS Check-out')
    image_check_in = fields.Binary(string='Ảnh Check-in')
    image_check_out = fields.Binary(string='Ảnh Check-out')