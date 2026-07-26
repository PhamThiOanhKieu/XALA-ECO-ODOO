# -*- coding: utf-8 -*-

import json
import base64
import hashlib
import hmac
import re

from odoo import http, fields
from odoo.http import request


class SePayController(http.Controller):

    @http.route(
        "/payment/sepay_direct/<int:payment_id>",
        type="http",
        auth="public",
        website=True,
        csrf=False,
    )
    def sepay_direct(self, payment_id, **kwargs):
        payment = request.env["xalaeco.payment"].sudo().browse(payment_id)

        if not payment.exists():
            return request.not_found()

        ICP = request.env["ir.config_parameter"].sudo()

        merchant_id = ICP.get_param("xalaeco.sepay_merchant_id")
        secret_key = ICP.get_param("xalaeco.sepay_secret_key")

        base_url = ICP.get_param("web.base.url")
        if "localhost" in base_url or "127.0.0.1" in base_url:
            # SePay bắt buộc success_url/webhook phải là URL công khai (không được localhost).
            # Trước đây domain ngrok cá nhân bị gắn cứng thẳng trong code — rất dễ bị lộ domain
            # dev nội bộ, và khi tunnel đổi (ngrok free đổi domain mỗi lần restart) sẽ phải sửa
            # code + build lại. Giờ đọc từ tham số hệ thống, cấu hình ở
            # Settings > Technical > System Parameters > 'xalaeco.public_base_url'.
            public_override = ICP.get_param("xalaeco.public_base_url")
            if public_override:
                base_url = public_override
            else:
                return request.make_response(
                    "<h3>Chưa cấu hình URL công khai (web.base.url đang là localhost). "
                    "Vui lòng cấu hình tham số hệ thống 'xalaeco.public_base_url' "
                    "(ví dụ domain thật hoặc URL ngrok hiện tại) trước khi thanh toán qua SePay.</h3>"
                )

        base_url = base_url.rstrip("/")

        if not merchant_id:
            return request.make_response("<h3>Chưa cấu hình Merchant ID</h3>")
        if not secret_key:
            return request.make_response("<h3>Chưa cấu hình Secret Key</h3>")

        amount_to_pay = payment.debt_amount if payment.debt_amount > 0 else payment.amount_due
        amount_str = str(int(amount_to_pay or 0))

        code_name = (payment.name or f"TT{payment.id}").strip()
        order_number = f"XALA_{payment.id}"
        customer_id_str = str(payment.id)
        order_desc = f"Thanhtoan_{code_name}".strip()

        payload = {
            "merchant": merchant_id,
            "operation": "PURCHASE",
            "payment_method": "BANK_TRANSFER",
            "currency": "VND",
            "order_amount": amount_str,
            "order_invoice_number": order_number,
            "order_description": order_desc,
            "customer_id": customer_id_str,
            "success_url": f"{base_url}/payment/sepay_success?invoice={code_name}&payment_id={payment.id}",
            "error_url": f"{base_url}/payment/sepay_error",
            "cancel_url": f"{base_url}/payment/sepay_cancel",
        }

        sign_string = ",".join([
            f"cancel_url={base_url}/payment/sepay_cancel",
            f"currency=VND",
            f"customer_id={customer_id_str}",
            f"error_url={base_url}/payment/sepay_error",
            f"merchant={merchant_id}",
            f"operation=PURCHASE",
            f"order_amount={amount_str}",
            f"order_description={order_desc}",
            f"order_invoice_number={order_number}",
            f"payment_method=BANK_TRANSFER",
            f"success_url={base_url}/payment/sepay_success?invoice={code_name}&payment_id={payment.id}",
        ])

        raw_hmac = hmac.new(
            secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256
        ).digest()

        signature = base64.b64encode(raw_hmac).decode("utf-8")
        payload["signature"] = signature

        return request.render(
            "XALA_ECO_ODOO.sepay_redirect",
            {
                "action": "https://pay-sandbox.sepay.vn/v1/checkout/init",
                "payload": payload,
            },
        )

    @http.route("/payment/sepay_success", type="http", auth="public", csrf=False)
    def sepay_success(self, **kwargs):
        """Cập nhật gạch nợ ngay khi khách nhảy vào trang Success"""
        invoice = kwargs.get('invoice') or kwargs.get('order_invoice_number') or ''
        payment_id_param = kwargs.get('payment_id')

        payment = False

        if payment_id_param and str(payment_id_param).isdigit():
            payment = request.env["xalaeco.payment"].sudo().browse(int(payment_id_param))

        if (not payment or not payment.exists()) and invoice:
            payment = request.env["xalaeco.payment"].sudo().search([
                '|', ('name', '=', invoice.strip()), ('vnp_txn_ref', '=', invoice.strip())
            ], limit=1)

        if payment and payment.exists():
            try:
                payment.sudo().write({
                    'amount_paid': payment.amount_due,
                    'payment_date': fields.Date.today(),
                    'payment_method': 'sepay',
                    'note': 'Đã thanh toán tự động qua SePay.',
                })
            except Exception as e:
                print("Lỗi cập nhật Success Redirect:", e)

        html = """
        <html>
            <head><meta charset="utf-8"/><title>Kết quả thanh toán</title></head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: green;">Thanh toán thành công!</h1>
                <p>Cảm ơn bạn đã thực hiện thanh toán. Hệ thống đã ghi nhận thành công.</p>
                <br/>
                <a href="/odoo/action-156" 
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

    @http.route("/payment/sepay_error", type="http", auth="public", csrf=False)
    def sepay_error(self, **kwargs):
        html = """
        <html>
            <head><meta charset="utf-8"/><title>Kết quả thanh toán</title></head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: red;">Thanh toán thất bại hoặc lỗi chữ ký.</h1>
                <br/>
                <a href="/odoo/action-156" 
                   style="background-color: #875A7B; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    Quay lại Odoo
                </a>
            </body>
        </html>
        """
        return request.make_response(html, headers=[('Content-Type', 'text/html')])

    @http.route("/payment/sepay_cancel", type="http", auth="public", csrf=False)
    def sepay_cancel(self, **kwargs):
        html = """
        <html>
            <head><meta charset="utf-8"/><title>Kết quả thanh toán</title></head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: #ff9f43;">Giao dịch đã bị hủy.</h1>
                <br/>
                <a href="/odoo/action-156" 
                   style="background-color: #875A7B; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    Quay lại Odoo
                </a>
            </body>
        </html>
        """
        return request.make_response(html, headers=[('Content-Type', 'text/html')])

    @http.route("/payment/sepay_ipn", type="http", auth="public", methods=["POST"], csrf=False)
    def sepay_ipn(self, **kwargs):
        """Xử lý Webhook từ SePay"""
        try:
            raw_data = request.httprequest.data
            data = json.loads(raw_data.decode("utf-8")) if raw_data else {}

            content = str(data.get("content") or data.get("order_description") or data.get("description") or "")
            invoice = str(data.get("order", {}).get("order_invoice_number") or data.get("order_invoice_number") or "")

            payment = False

            match_tt = re.search(r'(TT\d+)', content, re.IGNORECASE) or re.search(r'(TT\d+)', invoice, re.IGNORECASE)
            if match_tt:
                code_tt = match_tt.group(1).upper()
                payment = request.env["xalaeco.payment"].sudo().search([
                    '|', ('name', '=', code_tt), ('vnp_txn_ref', '=', code_tt)
                ], limit=1)

            if not payment or not payment.exists():
                match_xala = re.search(r'XALA[_\s]?(\d+)', invoice, re.IGNORECASE) or re.search(r'XALA[_\s]?(\d+)', content, re.IGNORECASE)
                if match_xala:
                    payment_id = int(match_xala.group(1))
                    payment = request.env["xalaeco.payment"].sudo().browse(payment_id)

            if payment and payment.exists():
                payment.sudo().write({
                    'amount_paid': payment.amount_due,
                    'payment_date': fields.Date.today(),
                    'payment_method': 'sepay',
                    'bank_transaction_code': str(data.get("referenceCode") or data.get("id") or invoice or ''),
                    'note': 'Đã thanh toán tự động qua SePay (IPN).',
                })

                if hasattr(payment, 'invoice_id') and payment.invoice_id:
                    try:
                        payment.invoice_id.sudo().write({'payment_state': 'paid'})
                    except Exception as e:
                        print("Loi update invoice_id:", e)

            return request.make_response(
                json.dumps({"success": True}), 
                headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}), 
                headers=[("Content-Type", "application/json")], 
                status=500
            )

    @http.route("/payment/sepay/status/<string:order_code>", type="http", auth="public", methods=["GET"], csrf=False)
    def sepay_status_check(self, order_code, **kwargs):
        status = "Waiting"
        try:
            payment = False
            if order_code.startswith("XALA_"):
                p_id = int(order_code.replace("XALA_", ""))
                payment = request.env["xalaeco.payment"].sudo().browse(p_id)
            elif order_code.startswith("TT"):
                payment = request.env["xalaeco.payment"].sudo().search([('name', '=', order_code)], limit=1)

            if payment and payment.exists():
                if payment.debt_amount == 0 or payment.state == 'paid':
                    status = "Paid"
        except Exception:
            pass

        return request.make_response(
            json.dumps({"status": status}),
            headers=[("Content-Type", "application/json")]
        )