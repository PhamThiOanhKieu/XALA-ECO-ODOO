from datetime import date, datetime
import json
import urllib.parse
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import vnpay_utils


class XalaEcoPayment(models.Model):
    _name = 'xalaeco.payment'
    _description = 'Thanh toán QR và công nợ XALA ECO'
    _order = 'contract_id desc nulls last, name asc'

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
        ('vnpay', 'VNPay'),
        ('momo', 'MoMo'),
        ('sepay', 'SePay'),
    ], string="Phương thức")

    bank_transaction_code = fields.Char(string='Mã giao dịch ngân hàng')
    bank_code = fields.Char(string='Mã ngân hàng', default='VCB')
    bank_account = fields.Char(string='Số tài khoản nhận', default='1046994985')
    account_name = fields.Char(string='Tên chủ tài khoản', default='PHAM THI OANH KIEU')

    transfer_content = fields.Char(string='Nội dung chuyển khoản', compute='_compute_transfer_content', store=True)
    qr_url = fields.Char(string='Link VietQR', compute='_compute_qr_url', store=True)
    qr_image = fields.Binary(string='QR thanh toán', compute='_compute_qr_image', store=False)

    vnp_txn_ref = fields.Char(string='Mã giao dịch VNPay (TxnRef)', copy=False)
    momo_txn_ref = fields.Char(string='Mã giao dịch MoMo (TxnRef)', copy=False)

    sepay_order_id = fields.Char(copy=False)
    sepay_order_code = fields.Char(copy=False)
    sepay_va_number = fields.Char(copy=False)
    sepay_qr = fields.Binary("QR SePay", attachment=True)

    sepay_expired_at = fields.Datetime(string="Hết hạn SePay", copy=False)
    sepay_status = fields.Char(string="Trạng thái SePay", copy=False)

    state = fields.Selection([
        ('unpaid', 'Chưa thanh toán'),
        ('partial', 'Thanh toán một phần'),
        ('paid', 'Đã thanh toán'),
    ], string='Trạng thái', compute='_compute_state', store=True)

    note = fields.Text(string='Ghi chú đối soát')
    invoice_id = fields.Many2one('account.move', string='Hóa đơn liên kết')

    # FIX: Bắt buộc thêm store=True để giao diện XML Odoo nhận diện ẩn/hiện nút
    xalaeco_contract_status = fields.Selection([
        ('active', 'Đang hiệu lực'),
        ('no_contract', 'Chưa có hợp đồng'),
    ], string='Trạng thái hợp đồng', compute='_compute_xalaeco_contract_status', store=True)

    # Các trường ảo phục vụ tự động import từ Excel
    payment_no = fields.Char(string='Mã thanh toán Excel')
    customer_code = fields.Char(string='Mã khách hàng Excel')
    customer_name = fields.Char(string='Tên khách hàng Excel')
    contract_code = fields.Char(string='Mã hợp đồng Excel')
    billing_period = fields.Char(string='Kỳ thanh toán Excel')
    month = fields.Char(string='Tháng Excel')
    year = fields.Char(string='Năm Excel')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('payment_no'):
                vals['name'] = vals['payment_no']
            elif vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('xalaeco.payment') or 'New'

            if vals.get('customer_code') and not vals.get('customer_id'):
                cust = self.env['xalaeco.customer'].search([('customer_code', '=', vals['customer_code'])], limit=1)
                if cust:
                    vals['customer_id'] = cust.id

            if vals.get('contract_code') and not vals.get('contract_id'):
                cont = self.env['xalaeco.contract'].search([('name', '=', vals['contract_code'])], limit=1)
                if cont:
                    vals['contract_id'] = cont.id

            if not vals.get('billing_id'):
                period_name = vals.get('billing_period')
                m_val = vals.get('month')
                y_val = vals.get('year')

                if period_name and '/' in period_name:
                    parts = period_name.split('/')
                    if len(parts) == 2:
                        m_val, y_val = parts[0].strip(), parts[1].strip()

                if m_val and y_val:
                    billing = self.env['xalaeco.billing'].search([('month', '=', m_val), ('year', '=', y_val)], limit=1)
                    if not billing:
                        billing = self.env['xalaeco.billing'].create({
                            'name': f'Kỳ thu phí Tháng {m_val}/{y_val}',
                            'month': m_val,
                            'year': y_val,
                            'state': 'collecting'
                        })
                    vals['billing_id'] = billing.id

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
            if not record.amount_paid or record.amount_paid <= 0:
                record.state = 'unpaid'
            elif record.amount_paid < record.amount_due:
                record.state = 'partial'
            else:
                record.state = 'paid'

    @api.depends('contract_id', 'customer_id')
    def _compute_xalaeco_contract_status(self):
        for record in self:
            contract = record.contract_id or self.env['xalaeco.contract'].search([
                ('customer_id', '=', record.customer_id.id),
            ], limit=1)
            
            # Cho phép nếu có contract
            if contract and getattr(contract, 'state', 'active') not in ['cancel', 'draft']:
                record.xalaeco_contract_status = 'active'
            else:
                record.xalaeco_contract_status = 'no_contract'

    def action_confirm_paid(self):
        """Xác nhận thanh toán thủ công"""
        for record in self:
            record.write({
                'amount_paid': record.amount_due,
                'payment_date': fields.Date.today(),
                'payment_method': 'sepay',
                'note': 'Đã xác nhận thanh toán.',
            })
        return True

    def action_reset_unpaid(self):
        for record in self:
            record.write({
                'amount_paid': 0.0,
                'payment_date': False,
                'bank_transaction_code': False,
                'payment_method': False,
                'note': 'Đã đưa về trạng thái chưa thanh toán.',
            })
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
            'vnp_Amount': int((self.debt_amount or self.amount_due or 0) * 100),
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

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError('Hóa đơn đã được tạo cho lượt thanh toán này!')

        contract = self.contract_id or self.env['xalaeco.contract'].search([
            ('customer_id', '=', self.customer_id.id),
        ], limit=1)

        if not contract:
            raise UserError(f"Khách hàng '{self.customer_id.name}' chưa gắn hợp đồng. Không thể xuất hóa đơn.")

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Hóa đơn bán hàng',
                'code': 'INV',
                'type': 'sale',
                'company_id': self.env.company.id,
            })

        partner = self.customer_id._get_or_create_partner()

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': journal.id,
            'xalaeco_customer_id': self.customer_id.id,
            'xalaeco_tax_code': getattr(self.customer_id, 'tax_code', False),
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [],
        }

        customer_type = getattr(self.customer_id, 'customer_type', 'company')

        if customer_type == 'household':
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'name': 'Phí dịch vụ thu gom rác thải sinh hoạt (Hộ dân)',
                'quantity': 1.0,
                'price_unit': getattr(self.customer_id, 'monthly_fee', 84000.0) or 84000.0,
            }))
        else:
            price = getattr(contract, 'service_fee', 0.0) or (getattr(contract, 'collection_fee', 0.0) + getattr(contract, 'transport_fee', 0.0)) or getattr(self.customer_id, 'monthly_fee', 0.0)
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'name': 'Dịch vụ thu gom và vận chuyển rác thải sinh hoạt',
                'quantity': 1.0,
                'price_unit': price,
            }))

        invoice = self.env['account.move'].create(invoice_vals)
        self.invoice_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Hóa đơn XALA ECO',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_pay_momo(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('web.base.url')

        return {
            'type': 'ir.actions.act_url',
            'url': f"{base_url}/payment/momo_direct/{self.id}",
            'target': 'self',
        }

    def action_pay_online(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        return {
            'type': 'ir.actions.act_url',
            'url': f"{base_url}/payment/checkout/{self.id}",
            'target': 'self',
        }

    def action_pay_sepay(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        return {
            "type": "ir.actions.act_url",
            "url": f"{base_url}/payment/sepay_direct/{self.id}",
            "target": "self",
        }