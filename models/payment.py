from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
import urllib.parse
import base64
import requests

from . import vnpay_utils


class XalaEcoPayment(models.Model):
    _name = 'xalaeco.payment'
    _description = 'Thanh toán QR và công nợ XALA ECO'

    name = fields.Char(string='Mã thanh toán', required=True, copy=False, default='New')

    customer_id = fields.Many2one('xalaeco.customer', string='Khách hàng', required=True)
    contract_id = fields.Many2one('xalaeco.contract', string='Hợp đồng')
    billing_id = fields.Many2one('xalaeco.billing', string='Kỳ thu phí')

    amount_due = fields.Float(string='Số tiền phải thu')
    amount_paid = fields.Float(string='Số tiền khách trả')
    debt_amount = fields.Float(string='Còn nợ', compute='_compute_debt', store=True)

    payment_date = fields.Date(string='Ngày thanh toán')
    payment_method = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('vnpay', 'Thanh toán VNPay'),
    ], string='Phương thức thanh toán')

    bank_transaction_code = fields.Char(string='Mã giao dịch ngân hàng')
    bank_code = fields.Char(string='Mã ngân hàng', default='VCB')
    bank_account = fields.Char(string='Số tài khoản nhận', default='1046994985')
    account_name = fields.Char(string='Tên chủ tài khoản', default='PHAM THI OANH KIEU')

    transfer_content = fields.Char(string='Nội dung chuyển khoản', compute='_compute_transfer_content', store=True)
    qr_url = fields.Char(string='Link VietQR', compute='_compute_qr_url', store=True)
    qr_image = fields.Binary(string='QR thanh toán', compute='_compute_qr_image', store=False)

    vnp_txn_ref = fields.Char(string='Mã giao dịch VNPay (TxnRef)', copy=False)
    
    # CHỈNH SỬA NGÀY 20/07/2026: Thêm trường lưu mã giao dịch MoMo Sandbox
    momo_txn_ref = fields.Char(string='Mã giao dịch MoMo (TxnRef)', copy=False)
    #--------Hết----------
    
    state = fields.Selection([
        ('unpaid', 'Chưa thanh toán'),
        ('partial', 'Thanh toán một phần'),
        ('paid', 'Đã thanh toán'),
    ], string='Trạng thái', compute='_compute_state', store=True)

    note = fields.Text(string='Ghi chú đối soát')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.payment') or 'New'
        return super().create(vals_list)

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.customer_id = self.contract_id.customer_id
            self.amount_due = self.contract_id.service_fee

    @api.depends('amount_due', 'amount_paid')
    def _compute_debt(self):
        for record in self:
            record.debt_amount = max((record.amount_due or 0) - (record.amount_paid or 0), 0)

    @api.depends('customer_id', 'billing_id')
    def _compute_transfer_content(self):
        for record in self:
            if record.customer_id and record.billing_id:
                record.transfer_content = f"{record.customer_id.customer_code}-T{record.billing_id.month}-{record.billing_id.year}"
            elif record.customer_id:
                record.transfer_content = f"{record.customer_id.customer_code}-XALA"
            else:
                record.transfer_content = ''

    @api.depends('amount_due', 'bank_account', 'bank_code', 'transfer_content', 'account_name')
    def _compute_qr_url(self):
        for record in self:
            if record.bank_code and record.bank_account:
                amount = int(record.amount_due or 0)
                content = urllib.parse.quote(record.transfer_content or '')
                acc_name = urllib.parse.quote(record.account_name or '')
                record.qr_url = (
                    f"https://img.vietqr.io/image/"
                    f"{record.bank_code}-{record.bank_account}-compact2.png"
                    f"?amount={amount}&addInfo={content}&accountName={acc_name}"
                )
            else:
                record.qr_url = ''

    @api.depends('qr_url')
    def _compute_qr_image(self):
        for record in self:
            record.qr_image = False

    @api.depends('amount_due', 'amount_paid')
    def _compute_state(self):
        for record in self:
            if not record.amount_paid:
                record.state = 'unpaid'
            elif record.amount_paid < record.amount_due:
                record.state = 'partial'
            else:
                record.state = 'paid'

    def action_confirm_paid(self):
        for record in self:
            record.amount_paid = record.amount_due
            record.payment_date = date.today()
            record.payment_method = 'cash'
            record.note = 'Đã xác nhận thu đủ tiền.'
        return True

    def action_reset_unpaid(self):
        for record in self:
            record.amount_paid = 0
            record.payment_date = False
            record.bank_transaction_code = False
            record.payment_method = False
            record.note = 'Đã đưa về trạng thái chưa thanh toán.'
        return True
    

    def action_pay_vnpay(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        tmn_code = ICP.get_param('xalaeco.vnp_tmn_code')
        secret_key = ICP.get_param('xalaeco.vnp_hash_secret')
        vnp_url = ICP.get_param('xalaeco.vnp_url', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
        base_url = ICP.get_param('web.base.url')

        if not tmn_code or not secret_key:
            raise UserError('Chưa cấu hình vnp_TmnCode hoặc vnp_HashSecret. Vào Settings > Technical > System Parameters để thêm.')

        from datetime import datetime
        now = datetime.now()
        txn_ref = now.strftime('%d%H%M%S')
        self.vnp_txn_ref = txn_ref

        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': tmn_code,
            'vnp_Locale': 'vn',
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': txn_ref,
            'vnp_OrderInfo': f'Thanh toan cho ma GD:{txn_ref}',
            'vnp_OrderType': 'other',
            'vnp_Amount': int((self.debt_amount or 0) * 100),
            'vnp_ReturnUrl': f'{base_url}/payment/vnpay_return?db=xala_chuan',
            'vnp_IpAddr': '127.0.0.1',
            'vnp_CreateDate': now.strftime('%Y%m%d%H%M%S'),
        }

        payment_url = vnpay_utils.build_payment_url(vnp_params, secret_key, vnp_url)

        return {
            'type': 'ir.actions.act_url',
            'url': payment_url,
            'target': 'self',
        }

    # CHỈNH SỬA NGÀY 20/07/2026: Hàm xử lý nút bấm chuyển hướng thanh toán qua MoMo Sandbox
    def action_pay_momo(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('web.base.url')
        
        # Chuyển hướng trình duyệt đến controller xử lý thanh toán MoMo của Odoo
        payment_url = f"{base_url}/payment/momo_direct/{self.id}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': payment_url,
            'target': 'self',
        }
    #--------Hết----------

    # ###############################################################################
    # CHỈNH SỬA NGÀY 20/07/2026: HÀM ĐIỀU HƯỚNG SANG TRANG THANH TOÁN CHUNG (CHECKOUT)
    # ###############################################################################
    def action_pay_online(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return {
            'type': 'ir.actions.act_url',
            'url': f"{base_url}/payment/checkout/{self.id}",
            'target': 'self',
        }
    #--------Hết----------