from odoo import models, fields, api, _
from odoo.exceptions import UserError
import uuid
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import math
import calendar
from datetime import datetime, date

class AccountMove(models.Model):
    _inherit = 'account.move'

    xalaeco_customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng XALA ECO')
    xalaeco_tax_code = fields.Char(string='Mã số thuế người mua')
    xalaeco_issuing_unit = fields.Char(string='Đơn vị xuất', default=' CƠ SỞ KINH DOANH MTV XALA ECO')
    xalaeco_digital_signature = fields.Binary(string='Chữ ký số giả lập')
    xalaeco_tax_verification_code = fields.Char(string='Mã xác thực cơ quan thuế')
    xalaeco_tax_send_time = fields.Datetime(string='Thời gian gửi cơ quan thuế')
    xalaeco_is_sent_to_tax = fields.Boolean(string='Đã gửi cơ quan thuế', default=False)
    xalaeco_lookup_qr_code = fields.Binary(string='QR code tra cứu', compute='_compute_xalaeco_lookup_qr_code')

    @api.depends('xalaeco_lookup_code')
    def _compute_xalaeco_lookup_qr_code(self):
        for move in self:
            code_val = f"https://tracuuhoadon.gdt.gov.vn?code={move.xalaeco_lookup_code or '0401234567'}"
            barcode_raw = self.env['ir.actions.report'].barcode('QR', code_val)
            move.xalaeco_lookup_qr_code = base64.b64encode(barcode_raw)

    xalaeco_serial = fields.Char(string='Ký hiệu hóa đơn', default='1C25TAA')
    xalaeco_payment_method = fields.Char(string='Hình thức thanh toán', default='Chuyển khoản')
    xalaeco_payment_term = fields.Char(string='Phương thức thanh toán', default='1 lần')
    xalaeco_service_from_date = fields.Date(string='Kỳ dịch vụ từ ngày')
    xalaeco_service_to_date = fields.Date(string='Kỳ dịch vụ đến ngày')
    xalaeco_amount_in_words = fields.Char(string='Số tiền bằng chữ', compute='_compute_xalaeco_amount_in_words')
    xalaeco_vietqr_url = fields.Char(string='Link VietQR thanh toán', compute='_compute_xalaeco_vietqr_url')
    xalaeco_lookup_code = fields.Char(string='Mã tra cứu hóa đơn', default=lambda self: self._generate_lookup_code())

    # --- Tab: Thông tin kỳ thu phí ---
    xalaeco_billing_period = fields.Char(string='Kỳ thu phí', help='Ví dụ: 07/2026')
    xalaeco_customer_type = fields.Selection([
        ('household', 'Hộ dân'),
        ('business', 'Hộ kinh doanh'),
        ('office', 'Văn phòng'),
        ('restaurant', 'Quán ăn'),
    ], string='Loại khách hàng')
    xalaeco_staff_name = fields.Char(string='Nhân viên phụ trách')
    xalaeco_note = fields.Text(string='Ghi chú')

    # --- Tab: Hóa đơn điện tử Việt Nam ---
    xalaeco_invoice_number = fields.Char(string='Số hóa đơn', compute='_compute_xalaeco_invoice_fields', store=True)
    xalaeco_issue_date = fields.Date(string='Ngày phát hành', compute='_compute_xalaeco_invoice_fields', store=True)
    xalaeco_company_tax_code = fields.Char(string='MST đơn vị', compute='_compute_xalaeco_invoice_fields', store=True)
    xalaeco_invoice_status = fields.Char(string='Trạng thái', compute='_compute_xalaeco_invoice_status')

    @api.depends('name', 'invoice_date', 'company_id', 'company_id.xalaeco_tax_code', 'company_id.vat')
    def _compute_xalaeco_invoice_fields(self):
        for move in self:
            move.xalaeco_invoice_number = move.name or ''
            move.xalaeco_issue_date = move.invoice_date
            move.xalaeco_company_tax_code = (
                move.company_id.xalaeco_tax_code or move.company_id.vat or '0401234567'
            )

    @api.depends('state', 'xalaeco_is_sent_to_tax', 'xalaeco_tax_verification_code')
    def _compute_xalaeco_invoice_status(self):
        for move in self:
            if move.xalaeco_tax_verification_code:
                move.xalaeco_invoice_status = 'Đã phát hành'
            elif move.state == 'posted':
                move.xalaeco_invoice_status = 'Đã xác nhận'
            elif move.state == 'cancel':
                move.xalaeco_invoice_status = 'Đã hủy'
            else:
                move.xalaeco_invoice_status = 'Nháp'

    def _generate_lookup_code(self):
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    @api.depends('amount_total')
    def _compute_xalaeco_amount_in_words(self):
        for move in self:
            amount = int(move.amount_total)
            move.xalaeco_amount_in_words = self._num_to_words_vi(amount)

    @api.depends('amount_total', 'name')
    def _compute_xalaeco_vietqr_url(self):
        import urllib.parse
        for move in self:
            company = move.company_id
            bank_code = company.xalaeco_bank_name or 'VCB'
            if 'Vietcombank' in bank_code or 'VCB' in bank_code:
                code = 'VCB'
            elif 'Vietin' in bank_code or 'CTG' in bank_code:
                code = 'CTG'
            elif 'BIDV' in bank_code:
                code = 'BIDV'
            else:
                code = 'VCB'
                
            acc = company.xalaeco_bank_account or '1042253873'
            acc_name = company.name or 'CƠ SỞ KINH DOANH MTV XALA ECO '
            amount = int(move.amount_total)
            content = move.name or 'XALAECO'
            
            url = (
                f"https://img.vietqr.io/image/"
                f"{code}-{acc}-compact2.png"
                f"?amount={amount}&addInfo={urllib.parse.quote(content)}&accountName={urllib.parse.quote(acc_name)}"
            )
            move.xalaeco_vietqr_url = url

    def _num_to_words_vi(self, num):
        if num == 0:
            return "Không đồng"
        
        units = ["", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
        tens = ["", "mười", "hai mươi", "ba mươi", "bốn mươi", "năm mươi", "sáu mươi", "bảy mươi", "tám mươi", "chín mươi"]
        
        def read_three_digits(n, has_higher=False):
            res = []
            h = n // 100
            t = (n % 100) // 10
            u = n % 10
            
            if h > 0 or has_higher:
                res.append(f"{units[h]} trăm")
            
            if t == 0:
                if u > 0 and (h > 0 or has_higher):
                    res.append("lẻ")
            elif t == 1:
                res.append("mười")
            else:
                res.append(f"{units[t]} mươi")
                
            if u == 1:
                if t > 1:
                    res.append("mốt")
                else:
                    res.append("một")
            elif u == 5:
                if t > 0:
                    res.append("lăm")
                else:
                    res.append("năm")
            elif u > 0:
                res.append(units[u])
                
            return " ".join(res)
            
        groups = []
        temp = num
        while temp > 0:
            groups.append(temp % 1000)
            temp = temp // 1000
            
        words = []
        labels = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
        
        for i in range(len(groups)):
            val = groups[i]
            if val > 0:
                has_higher = (i < len(groups) - 1) or (groups[i] // 100 > 0)
                three_word = read_three_digits(val, has_higher=has_higher)
                label = labels[i]
                if label:
                    words.insert(0, f"{three_word} {label}")
                else:
                    words.insert(0, three_word)
                    
        words_str = " ".join(words).strip()
        if words_str:
            words_str = words_str[0].upper() + words_str[1:] + " đồng chẵn./."
        return words_str

    @api.onchange('xalaeco_customer_id')
    def _onchange_xalaeco_customer_id(self):
        if self.xalaeco_customer_id:
            self.xalaeco_tax_code = self.xalaeco_customer_id.tax_code
            partner = self.xalaeco_customer_id._get_or_create_partner()
            self.partner_id = partner.id

            import calendar
            today = date.today()
            self.xalaeco_service_from_date = today.replace(day=1)
            self.xalaeco_service_to_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])

            if self.company_id and self.company_id.name:
                self.xalaeco_issuing_unit = self.company_id.name

            # Tự động tạo dòng chi tiết hóa đơn nếu chưa có
            if not self.invoice_line_ids:
                lines = []
                cust_type = self.xalaeco_customer_id.customer_type
                if cust_type == 'household':
                    lines.append((0, 0, {
                        'name': 'Phí dịch vụ thu gom rác thải sinh hoạt (Hộ dân)',
                        'quantity': 1.0,
                        'price_unit': self.xalaeco_customer_id.monthly_fee or 84000.0,
                    }))
                else:
                    contract = self.env['xalaeco.contract'].search([
                        ('customer_id', '=', self.xalaeco_customer_id.id),
                        ('state', '=', 'active'),
                    ], limit=1)
                    if contract:
                        # Dùng phí dịch vụ tổng hợp từ hợp đồng (bao gồm cả phí thu gom và xử lý)
                        lines.append((0, 0, {
                            'name': 'Dịch vụ thu gom và vận chuyển rác thải sinh hoạt',
                            'quantity': 1.0,
                            'price_unit': contract.service_fee or (contract.collection_fee + contract.transport_fee) or 0.0,
                        }))
                    else:
                        # Fallback nếu không có hợp đồng
                        lines.append((0, 0, {
                            'name': 'Dịch vụ thu gom và vận chuyển rác thải sinh hoạt',
                            'quantity': 1.0,
                            'price_unit': self.xalaeco_customer_id.monthly_fee or 0.0,
                        }))
                self.invoice_line_ids = lines

    def action_xalaeco_populate_lines(self):
        self.ensure_one()
        self._onchange_xalaeco_customer_id()
        return True

    def _draw_circular_seal(self, move):
        # Create a square canvas for con dấu only (200x200 pixels)
        img = Image.new('RGBA', (200, 200), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # --- GHÉP CON DẤU THỰC TẾ (company_stamp.png) ---
        import os
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        stamp_path = os.path.join(addon_path, 'static', 'src', 'img', 'company_stamp.png')
        
        if os.path.exists(stamp_path):
            try:
                stamp_img = Image.open(stamp_path).convert("RGBA")
                
                # Làm sạch nền trắng của con dấu để có độ trong suốt tuyệt đối (Transparency)
                datas = stamp_img.getdata()
                newData = []
                for item in datas:
                    if item[0] > 240 and item[1] > 240 and item[2] > 240:
                        newData.append((255, 255, 255, 0))
                    else:
                        newData.append(item)
                stamp_img.putdata(newData)
                
                # Resize con dấu tròn về kích thước 180x180 để tối ưu không gian hiển thị trong canvas 200x200
                stamp_img = stamp_img.resize((180, 180), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
                
                # Dán đè vào vị trí (x=10, y=10) để căn giữa
                img.paste(stamp_img, (10, 10), stamp_img)
            except Exception as e:
                draw.ellipse([10, 10, 190, 190], outline=(211, 47, 47, 255), width=4)
        else:
            draw.ellipse([10, 10, 190, 190], outline=(211, 47, 47, 255), width=4)
            
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue())

    def action_post(self):
        for move in self:
            if move.move_type == 'out_invoice' and move.xalaeco_customer_id:
                contract = self.env['xalaeco.contract'].search([
                    ('customer_id', '=', move.xalaeco_customer_id.id),
                    ('state', 'in', ['active', 'near_expired']),
                ], limit=1)
                if not contract:
                    raise UserError(_("Khách hàng '%s' không có hợp đồng đang hiệu lực. Không thể xuất hóa đơn.") % move.xalaeco_customer_id.name)

        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'out_invoice':
                company = move.company_id
                seal_image = self._draw_circular_seal(move)
                move.xalaeco_digital_signature = seal_image
                company.sudo().write({'xalaeco_company_seal': seal_image})
        return res

    def action_xalaeco_send_to_tax_authority(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError('Chỉ có thể gửi cơ quan thuế khi hóa đơn đã được xác nhận!')
        if self.xalaeco_tax_verification_code:
            raise UserError('Hóa đơn này đã được gửi cơ quan thuế trước đó!')
            
        import requests
        import json
        
        payload = {
            'tax_code': self.xalaeco_tax_code or self.partner_id.vat or '',
            'company_tax_code': self.company_id.xalaeco_tax_code or self.company_id.vat or '0401234567',
            'invoice_no': self.name,
            'amount': self.amount_total,
            'date': str(self.invoice_date or datetime.now().date())
        }
        
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or 'http://localhost:8069'
        url = f"{base_url}/xala_eco/tax_api/submit"
        
        verification_code = False
        send_time = fields.Datetime.now()
        
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=json.dumps({'params': payload}), headers=headers, timeout=5)
            if response.status_code == 200:
                res_data = response.json()
                result = res_data.get('result', {})
                if result.get('status') == 'success':
                    verification_code = result.get('verification_code')
                    send_time_str = result.get('send_time')
                    if send_time_str:
                        send_time = fields.Datetime.from_string(send_time_str)
                else:
                    raise UserError(f"API báo lỗi từ cơ quan thuế: {result.get('message')}")
            else:
                raise UserError(f"Không thể kết nối đến Virtual Tax API (HTTP {response.status_code})")
        except Exception as e:
            today_str = fields.Date.context_today(self).strftime('%Y%m%d')
            random_str = str(uuid.uuid4())[:8].upper()
            verification_code = f"TCT-{today_str}-{random_str}"
            send_time = fields.Datetime.now()
            
        self.write({
            'xalaeco_tax_verification_code': verification_code,
            'xalaeco_tax_send_time': send_time,
            'xalaeco_is_sent_to_tax': True
        })
        
        # Giả lập tin nhắn phản hồi từ Tổng cục Thuế trong phần Chatter
        tax_partner = self.env['res.partner'].sudo().search([('name', '=', 'Tổng cục Thuế')], limit=1)
        if not tax_partner:
            tax_partner = self.env['res.partner'].sudo().create({
                'name': 'Tổng cục Thuế',
                'email': 'feedback@gdt.gov.vn',
                'company_id': False,
            })
            
        local_send_time = fields.Datetime.context_timestamp(self, send_time)
        from markupsafe import Markup
        message_body = Markup(f"""
        <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
            <p style="color: #2e7d32; font-weight: bold; margin-bottom: 5px;">[HỆ THỐNG XÁC THỰC HÓA ĐƠN ĐIỆN TỬ - TỔNG CỤC THUẾ]</p>
            <p style="margin: 2px 0;">Đã tiếp nhận và xác thực thành công dữ liệu hóa đơn số <strong>{self.name}</strong>.</p>
            <p style="margin: 2px 0;">Mã số xác thực cấp bởi cơ quan thuế: <strong style="color: #d32f2f; font-size: 11px;">{verification_code}</strong></p>
        </div>
        """)
        self.message_post(
            body=message_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=tax_partner.id
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gửi cơ quan thuế thành công!'),
                'type': 'success',
                'sticky': False,
            },
            'next': {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        }

    def button_draft(self):
        for move in self:
            if move.move_type == 'out_invoice':
                raise UserError(_("Chức năng 'Đặt lại thành nháp' đã bị loại bỏ cho hóa đơn bán hàng."))
        return super(AccountMove, self).button_draft()

    def _message_track(self, fields_iter, initial_values_dict):
        return {}

    def message_post(self, **kwargs):
        tax_partner = self.env['res.partner'].sudo().search([('name', '=', 'Tổng cục Thuế')], limit=1)
        author_id = kwargs.get('author_id')
        if tax_partner and author_id == tax_partner.id:
            return super(AccountMove, self).message_post(**kwargs)
        return self.env['mail.message']
