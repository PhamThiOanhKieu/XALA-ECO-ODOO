import logging
_logger = logging.getLogger(__name__)
from odoo import http
from odoo.http import request
from datetime import date

from odoo.addons.xala_eco_odoo.models import vnpay_utils


class VNPayController(http.Controller):

    @http.route('/payment/vnpay_return', type='http', auth='public', website=False, csrf=False)
    def vnpay_return(self, **kwargs):
        _logger.info("VNPay return called with params: %s", kwargs)
        ICP = request.env['ir.config_parameter'].sudo()
        secret_key = ICP.get_param('xalaeco.vnp_hash_secret')

        is_valid = vnpay_utils.verify_return_params(kwargs, secret_key)
        _logger.info("VNPay params: %s", kwargs)
        _logger.info("VNPay is_valid: %s, response_code: %s", is_valid, kwargs.get('vnp_ResponseCode'))

        response_code = kwargs.get('vnp_ResponseCode')
        txn_ref = kwargs.get('vnp_TxnRef')
        bank_txn_no = kwargs.get('vnp_BankTranNo') or kwargs.get('vnp_TransactionNo')

        if is_valid and response_code == '00':
            payment = request.env['xalaeco.payment'].sudo().search(
                [('vnp_txn_ref', '=', txn_ref)], limit=1
            )
            if payment:
                payment.write({
                    'amount_paid': payment.amount_paid + payment.debt_amount,
                    'payment_date': date.today(),
                    'payment_method': 'vnpay',
                    'bank_transaction_code': bank_txn_no or txn_ref,
                    'note': 'Đã thanh toán tự động qua VNPay.',
                })
            message = 'Thanh toán thành công!'
            success = True
        else:
            message = 'Thanh toán thất bại hoặc chữ ký không hợp lệ.'
            success = False

        html = f"""
        <html>
            <head><meta charset="utf-8"/><title>Kết quả thanh toán</title></head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: {'green' if success else 'red'};">{message}</h1>
                <p>Mã giao dịch: {txn_ref or ''}</p>
                <br/>
                <a href="/odoo/xalaeco-payment" 
                   style="background-color: #875A7B; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    Quay lại Odoo
                </a>
            </body>
        </html>
        """
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html'),
            ('ngrok-skip-browser-warning', 'true'),
        ])

    @http.route('/payment/pay/<int:payment_id>', type='http', auth='public', csrf=False)
    def payment_page(self, payment_id, **kwargs):
        payment = request.env['xalaeco.payment'].sudo().browse(payment_id)
        if not payment.exists():
            return request.make_response(
                '<h1>Không tìm thấy thông tin thanh toán</h1>',
                headers=[('Content-Type', 'text/html')]
            )
        
        ICP = request.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('web.base.url')
        
        html = f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <title>Thanh toán - XALA ECO</title>
                <style>
                    body {{ font-family: sans-serif; text-align: center; padding: 40px; }}
                    .amount {{ font-size: 32px; color: #e63946; font-weight: bold; }}
                    .info {{ margin: 20px auto; max-width: 400px; text-align: left; }}
                    .btn {{ background: #875A7B; color: white; padding: 12px 24px; 
                            border: none; border-radius: 6px; font-size: 16px; 
                            text-decoration: none; }}
                </style>
            </head>
            <body>
                <h2>Thanh toán phí thu gom rác - XALA ECO</h2>
                <div class="info">
                    <p><b>Khách hàng:</b> {payment.customer_id.name}</p>
                    <p><b>Kỳ thu phí:</b> Tháng {payment.billing_id.month}/{payment.billing_id.year}</p>
                    <p><b>Số tiền:</b> <span class="amount">{int(payment.amount_due):,}đ</span></p>
                </div>
                <br/>
                <a href="{base_url}/web/login?redirect=/odoo/xalaeco-payment/{payment.id}" 
                   class="btn">Thanh toán ngay</a>
            </body>
        </html>
        """
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html'),
            ('ngrok-skip-browser-warning', 'true'),
        ])
    
    @http.route('/payment/vnpay_direct/<int:payment_id>', type='http', auth='public', csrf=False)
    def vnpay_direct(self, payment_id, **kwargs):
        payment = request.env['xalaeco.payment'].sudo().browse(payment_id)
        if not payment.exists():
            return request.make_response(
                '<h1>Không tìm thấy thông tin thanh toán</h1>',
                headers=[('Content-Type', 'text/html')]
            )
        
        ICP = request.env['ir.config_parameter'].sudo()
        tmn_code = ICP.get_param('xalaeco.vnp_tmn_code')
        secret_key = ICP.get_param('xalaeco.vnp_hash_secret')
        vnp_url = ICP.get_param('xalaeco.vnp_url', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
        base_url = ICP.get_param('web.base.url')

        from datetime import datetime
        now = datetime.now()
        txn_ref = now.strftime('%d%H%M%S')
        payment.sudo().write({'vnp_txn_ref': txn_ref})

        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': tmn_code,
            'vnp_Locale': 'vn',
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': txn_ref,
            'vnp_OrderInfo': f'Thanh toan cho ma GD:{txn_ref}',
            'vnp_OrderType': 'other',
            'vnp_Amount': int((payment.debt_amount or 0) * 100),
            'vnp_ReturnUrl': f'{base_url}/payment/vnpay_return?db=xala_chuan',
            'vnp_IpAddr': '127.0.0.1',
            'vnp_CreateDate': now.strftime('%Y%m%d%H%M%S'),
        }

        payment_url = vnpay_utils.build_payment_url(vnp_params, secret_key, vnp_url)
        
        return request.redirect(payment_url, local=False)