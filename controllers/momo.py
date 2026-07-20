# -*- coding: utf-8 -*-
import logging
import uuid
from odoo import http
from odoo.http import request
from datetime import date
from ..models import momo_utils

_logger = logging.getLogger(__name__)

class MoMoController(http.Controller):

    @http.route('/payment/momo_direct/<int:payment_id>', type='http', auth='public', csrf=False)
    def momo_direct(self, payment_id, **kwargs):
        """
        Định tuyến nhận lệnh từ Odoo, khởi tạo giao dịch và chuyển hướng khách hàng sang MoMo.
        """
        payment = request.env['xalaeco.payment'].sudo().browse(payment_id)
        if not payment.exists():
            return request.make_response(
                '<h1>Không tìm thấy thông tin thanh toán</h1>',
                headers=[('Content-Type', 'text/html')]
            )

        # Đọc cấu hình từ System Parameters
        ICP = request.env['ir.config_parameter'].sudo()
        partner_code = ICP.get_param('xalaeco.momo_partner_code', 'MOMO')
        access_key = ICP.get_param('xalaeco.momo_access_key')
        secret_key = ICP.get_param('xalaeco.momo_secret_key')
        momo_endpoint = ICP.get_param('xalaeco.momo_url', 'https://test-payment.momo.vn/v2/gateway/api/create')
        base_url = ICP.get_param('web.base.url')

        if not access_key or not secret_key:
            return request.make_response(
                '<h1>Lỗi: Chưa cấu hình tham số MoMo (access_key, secret_key) trong System Parameters!</h1>',
                headers=[('Content-Type', 'text/html')]
            )

        # Tạo mã giao dịch duy nhất cho MoMo
        order_id = f"MOMO_{payment.id}_{uuid.uuid4().hex[:6]}"
        request_id = f"REQ_{payment.id}_{uuid.uuid4().hex[:6]}"
        
        # Lưu mã giao dịch tạm thời để đối soát khi nhận kết quả
        payment.sudo().write({'momo_txn_ref': order_id})

        # Chuẩn bị gói dữ liệu gửi lên MoMo
        params = {
            'partnerCode': partner_code,
            'partnerName': 'XALA ECO',
            'storeId': 'XalaEcoStore',
            'requestId': request_id,
            'amount': int(payment.debt_amount or 0),
            'orderId': order_id,
            'orderInfo': f'Thanh toan phi thu gom rac XALA ECO - Ma HD:{payment.name}',
            'redirectUrl': f"{base_url}/payment/momo_return",
            'ipnUrl': f"{base_url}/payment/momo_return",
            'lang': 'vi',
            'extraData': '',
            'requestType': 'captureWallet'
        }

        # Gọi file tiện ích băm chữ ký và lấy link thanh toán
        pay_url = momo_utils.build_payment_url(params, access_key, secret_key, momo_endpoint)

        if pay_url:
            # Chuyển hướng người dùng sang trang thanh toán MoMo Sandbox
            return request.redirect(pay_url, local=False)
        else:
            return request.make_response(
                '<h1>Lỗi: Không thể kết nối hoặc khởi tạo liên kết thanh toán với Ví MoMo!</h1>',
                headers=[('Content-Type', 'text/html')]
            )

    @http.route('/payment/momo_return', type='http', auth='public', methods=['GET', 'POST'], website=False, csrf=False)
    def momo_return(self, **kwargs):
        """
        Đón nhận phản hồi kết quả giao dịch tự động của MoMo gửi về, đối soát chữ ký số và cập nhật hóa đơn.
        """
        _logger.info("MoMo return called with params: %s", kwargs)
        
        # Đọc khóa bí mật để kiểm thử đối soát chữ ký
        ICP = request.env['ir.config_parameter'].sudo()
        secret_key = ICP.get_param('xalaeco.momo_secret_key')

        # Xác thực tính toàn vẹn của chữ ký số
        is_valid = momo_utils.verify_signature(kwargs, secret_key)
        
        result_code = kwargs.get('resultCode')
        order_id = kwargs.get('orderId')
        trans_id = kwargs.get('transId')
        message = kwargs.get('message', '')

        # Chuyển đổi mã thành số nguyên để đối soát (MoMo trả về resultCode=0 khi thành công)
        try:
            result_code_int = int(result_code) if result_code is not None else -1
        except ValueError:
            result_code_int = -1

        success = False
        html_msg = 'Thanh toán thất bại hoặc chữ ký bảo mật không hợp lệ.'

        if is_valid and result_code_int == 0:
            payment = request.env['xalaeco.payment'].sudo().search(
                [('momo_txn_ref', '=', order_id)], limit=1
            )
            if payment:
                # Tiến hành cập nhật công nợ sang đã thu tiền
                payment.write({
                    'amount_paid': payment.amount_paid + payment.debt_amount,
                    'payment_date': date.today(),
                    'payment_method': 'momo',
                    'bank_transaction_code': trans_id or order_id,
                    'note': 'Đã thanh toán tự động thành công qua Ví MoMo.',
                })
                html_msg = 'Thanh toán qua Ví MoMo thành công!'
                success = True
            else:
                html_msg = 'Lỗi: Xác thực thành công nhưng không tìm thấy bản ghi thanh toán tương ứng.'
        else:
            if result_code_int != 0:
                html_msg = f"Giao dịch thất bại: {message} (Mã lỗi: {result_code})"

        # Giao diện thông báo kết quả trả về cho khách hàng
        html = f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <title>Kết quả thanh toán MoMo</title>
            </head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: {'green' if success else 'red'};">{html_msg}</h1>
                <p>Mã hóa đơn giao dịch: {order_id or ''}</p>
                <p>Mã tham chiếu MoMo: {trans_id or ''}</p>
                <br/>
                <!-- CHỈNH SỬA NGÀY 21/07/2026: Sửa link quay lại Odoo -->
                <a href="/odoo/action-93" 
                   style="background-color: #A50064; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Quay lại Odoo
                </a>
                <!-- --------Hết---------- -->
            </body>
        </html>
        """
        # Nếu là request IPN (máy chủ gọi ngầm qua phương thức POST), MoMo yêu cầu phản hồi HTTP 204
        if request.httprequest.method == 'POST':
            return request.make_response('', status=204)

        return request.make_response(html, headers=[
            ('Content-Type', 'text/html'),
            ('ngrok-skip-browser-warning', 'true'),
        ])
