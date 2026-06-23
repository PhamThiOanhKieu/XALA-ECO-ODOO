from odoo import models, fields, api
from datetime import date
import urllib.parse
import base64
import requests

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
        ('bank', 'Chuyển khoản QR'),
    ], string='Phương thức thanh toán', default='bank')

    bank_transaction_code = fields.Char(string='Mã giao dịch ngân hàng')
    bank_code = fields.Char(string='Mã ngân hàng', default='VCB')
    bank_account = fields.Char(string='Số tài khoản nhận', default='1046994985')
    account_name = fields.Char(string='Tên chủ tài khoản', default='PHAM THI OANH KIEU')

    transfer_content = fields.Char(string='Nội dung chuyển khoản', compute='_compute_transfer_content', store=True)
    qr_url = fields.Char(string='Link VietQR', compute='_compute_qr_url', store=True)
    qr_image = fields.Binary(string='QR thanh toán', compute='_compute_qr_image', store=True)

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
            if record.qr_url:
                try:
                    response = requests.get(record.qr_url, timeout=10)
                    if response.status_code == 200:
                        record.qr_image = base64.b64encode(response.content)
                except Exception:
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
            record.note = 'Đã xác nhận thu đủ tiền.'
        return True

    def action_reset_unpaid(self):
        for record in self:
            record.amount_paid = 0
            record.payment_date = False
            record.bank_transaction_code = False
            record.note = 'Đã đưa về trạng thái chưa thanh toán.'
        return True