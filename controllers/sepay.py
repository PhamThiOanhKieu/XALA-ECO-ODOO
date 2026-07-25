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
        if "localhost" in base_url:
            base_url = "https://jump-darkness-rubdown.ngrok-free.dev"
            
        base_url = base_url.rstrip('/')

        if not merchant_id:
            return request.make_response("<h3>Chưa cấu hình Merchant ID</h3>")
        if not secret_key:
            return request.make_response("<h3>Chưa cấu hình Secret Key</h3>")

        # Lấy số tiền cần thanh toán
        amount_to_pay = payment.debt_amount if payment.debt_amount > 0 else 0.0
        amount_str = str(int(amount_to_pay))
        order_number = f"INV_{payment.id}"
        customer_id_str = str(payment.id)
        order_desc = f"Thanhtoan_{payment.name}".strip()

        payload = {
            "merchant": merchant_id,
            "operation": "PURCHASE",
            "payment_method": "BANK_TRANSFER",
            "currency": "VND",
            "order_amount": amount_str,
            "order_invoice_number": order_number,
            "order_description": order_desc,
            "customer_id": customer_id_str,
            "success_url": f"{base_url}/payment/sepay_success?invoice={order_number}",
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
            f"success_url={base_url}/payment/sepay_success?invoice={order_number}",
        ])

        raw_hmac = hmac.new(
            secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256
        ).digest()
        
        signature = base64.b64encode(raw_hmac).decode("utf-8")
        payload["signature"] = signature

        return request.render(
            "xalaeco_management.sepay_redirect",
            {
                "action": "https://pay-sandbox.sepay.vn/v1/checkout/init",
                "payload": payload,
            },
        )

    @http.route("/payment/sepay_success", type="http", auth="public", csrf=False)
    def sepay_success(self, **kwargs):
        """Tự động cập nhật gạch nợ ngay khi khách quay lại trang Success"""
        invoice = kwargs.get('order_invoice_number') or kwargs.get('invoice')
        
        if invoice and invoice.startswith("INV_"):
            try:
                payment_id = int(invoice.replace("INV_", ""))
                payment = request.env["xalaeco.payment"].sudo().browse(payment_id)
                if payment.exists() and payment.debt_amount > 0:
                    amount_to_pay = payment.debt_amount
                    write_vals = {
                        'amount_paid': payment.amount_paid + amount_to_pay,
                        'debt_amount': 0.0,
                        'payment_date': fields.Date.today(),
                        'payment_method': 'sepay',  # <-- Điền 'sepay' vào đây là cột Phương thức sẽ hiện chữ SePay!
                        'bank_transaction_code': str(data.get("referenceCode") or data.get("id") or invoice),
                        'note': 'Đã thanh toán tự động qua SePay.',
                        }
                    if hasattr(payment, 'state'):
                        write_vals['state'] = 'paid'
                    if hasattr(payment, 'status'):
                        write_vals['status'] = 'paid'
                        
                    payment.write(write_vals)
                    print(f"--> [SUCCESS REDIRECT] UPDATED ODOO FOR {invoice}")
            except Exception as e:
                print("Lỗi cập nhật Success Redirect:", e)

        html = """
        <html>
            <head><meta charset="utf-8"/><title>Kết quả thanh toán</title></head>
            <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                <h1 style="color: green;">Thanh toán thành công!</h1>
                <p>Cảm ơn bạn đã thực hiện thanh toán. Hệ thống đã ghi nhận đơn hàng.</p>
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
        """Xử lý IPN/Webhook từ SePay chuẩn xác tuyệt đối"""
        try:
            raw_data = request.httprequest.data
            data = json.loads(raw_data.decode("utf-8")) if raw_data else {}
            
            print("==================== SEPAY IPN RECEIVED ====================")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("===========================================================")

            invoice = data.get("order", {}).get("order_invoice_number") or data.get("order_invoice_number")

            if not invoice and "content" in data:
                content = str(data.get("content", ""))
                match = re.search(r'INV[_\s]?(\d+)', content, re.IGNORECASE)
                if match:
                    invoice = f"INV_{match.group(1)}"

            payment = False
            if invoice and invoice.startswith("INV_"):
                payment_id = int(invoice.replace("INV_", ""))
                payment = request.env["xalaeco.payment"].sudo().browse(payment_id)

            if payment and payment.exists():
                amount_to_pay = payment.debt_amount if payment.debt_amount > 0 else 0.0
                write_vals = {
                                        'amount_paid': payment.amount_paid + amount_to_pay,
                                        'debt_amount': 0.0,
                                        'payment_date': fields.Date.today(),
                                        'payment_method': 'sepay',  # <-- Điền 'sepay' vào đây là cột Phương thức sẽ hiện chữ SePay!
                                        'bank_transaction_code': str(data.get("referenceCode") or data.get("id") or invoice),
                                        'note': 'Đã thanh toán tự động qua SePay.',
                                        }
                if hasattr(payment, 'state'):
                    write_vals['state'] = 'paid'
                if hasattr(payment, 'status'):
                    write_vals['status'] = 'paid'

                payment.write(write_vals)
                print(f" SUCCESS UPDATED ODOO FOR INVOICE: {invoice}")

            return request.make_response(
                json.dumps({"success": True}), 
                headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            print(" IPN ERROR:", str(e))
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}), 
                headers=[("Content-Type", "application/json")], 
                status=500
            )

    @http.route("/payment/sepay/status/<string:order_code>", type="http", auth="public", methods=["GET"], csrf=False)
    def sepay_status_check(self, order_code, **kwargs):
        """API cho JS Polling kiểm tra trạng thái đơn hàng"""
        status = "Waiting"
        try:
            if order_code.startswith("INV_"):
                payment_id = int(order_code.replace("INV_", ""))
                payment = request.env["xalaeco.payment"].sudo().browse(payment_id)
                if payment.exists() and (payment.debt_amount == 0 or getattr(payment, 'state', '') in ['paid', 'done']):
                    status = "Paid"
        except Exception:
            pass
            
        return request.make_response(
            json.dumps({"status": status}),
            headers=[("Content-Type", "application/json")]
        )

    @http.route("/test_sepay", type="http", auth="public", website=True)
    def test_sepay(self, **kw):
        return "OK SEPAY"