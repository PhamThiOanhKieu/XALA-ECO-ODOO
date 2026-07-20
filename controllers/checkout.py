# -*- coding: utf-8 -*-
# ###############################################################################
# CHỈNH SỬA NGÀY 20/07/2026: TẠO FILE ĐIỀU HƯỚNG TRANG THANH TOÁN TRUNG GIAN CHUNG
# ###############################################################################

from odoo import http
from odoo.http import request
import urllib.parse

class CheckoutController(http.Controller):

    @http.route('/payment/checkout/<int:payment_id>', type='http', auth='public', csrf=False)
    def payment_checkout(self, payment_id, **kwargs):
        # Lấy thông tin hóa đơn cần thanh toán
        payment = request.env['xalaeco.payment'].sudo().browse(payment_id)
        if not payment.exists():
            return "<h1>Lỗi: Hóa đơn thanh toán không tồn tại!</h1>"

        if payment.state == 'paid':
            return """
            <html>
                <head>
                    <meta charset="utf-8"/>
                    <title>Hóa đơn đã được thanh toán</title>
                    <style>
                        body { font-family: 'Segoe UI', Roboto, sans-serif; text-align: center; padding-top: 100px; background-color: #f8f9fa; color: #333; }
                        .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: inline-block; max-width: 450px; }
                        h1 { color: #28a745; margin-bottom: 10px; }
                        a { display: inline-block; margin-top: 20px; background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>✓ Đã Thanh Toán</h1>
                        <p>Hóa đơn <strong>#""" + str(payment.name) + """</strong> đã hoàn tất thanh toán trước đó.</p>
                        <!-- CHỈNH SỬA NGÀY 21/07/2026: Sửa link quay lại Odoo -->
                        <a href="/odoo/action-93">Quay lại Odoo</a>
                        <!-- --------Hết---------- -->
                    </div>
                </body>
            </html>
            """

        # Định dạng tiền tệ VND
        amount_fmt = f"{int(payment.debt_amount or 0):,}"
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')


        # Trả về trang Web Checkout phong cách Premium, hiện đại
        html = f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
                <title>Cổng Thanh Toán - XALA ECO</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', -apple-system, sans-serif;
                        background: radial-gradient(circle at 50% 50%, #1e1e2f 0%, #0f0f1a 100%);
                        color: #f3f3f6;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{
                        background: rgba(255, 255, 255, 0.04);
                        backdrop-filter: blur(20px);
                        border: 1px rgba(255, 255, 255, 0.08) solid;
                        border-radius: 24px;
                        padding: 40px;
                        width: 100%;
                        max-width: 500px;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
                        text-align: center;
                    }}
                    .logo {{
                        font-size: 26px;
                        font-weight: 800;
                        letter-spacing: 1px;
                        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        margin-bottom: 25px;
                    }}
                    .bill-info {{
                        background: rgba(255, 255, 255, 0.03);
                        border-radius: 16px;
                        padding: 20px;
                        margin-bottom: 30px;
                        text-align: left;
                        border: 1px rgba(255, 255, 255, 0.04) solid;
                    }}
                    .bill-row {{
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 12px;
                        font-size: 14px;
                    }}
                    .bill-row:last-child {{
                        margin-bottom: 0;
                        border-top: 1px rgba(255, 255, 255, 0.1) dashed;
                        padding-top: 12px;
                    }}
                    .label {{ color: #a0a0b0; }}
                    .val {{ font-weight: 600; color: #fff; }}
                    .val.price {{ font-size: 20px; color: #00f2fe; }}
                    
                    .section-title {{
                        font-size: 15px;
                        color: #a0a0b0;
                        margin-bottom: 15px;
                        text-align: left;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    
                    .btn-list {{
                        display: flex;
                        flex-direction: column;
                        gap: 15px;
                        margin-bottom: 30px;
                    }}
                    .pay-btn {{
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 12px;
                        padding: 16px;
                        border-radius: 14px;
                        text-decoration: none;
                        font-weight: bold;
                        font-size: 15px;
                        transition: all 0.3s ease;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-vnpay {{
                        background: #005a9e;
                        color: #fff;
                    }}
                    .btn-vnpay:hover {{
                        background: #0078d4;
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(0, 90, 158, 0.4);
                    }}
                    .btn-momo {{
                        background: #a50064;
                        color: #fff;
                    }}
                    .btn-momo:hover {{
                        background: #c20075;
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(165, 0, 100, 0.4);
                    }}
                    
                    .qr-section {{
                        background: rgba(255, 255, 255, 0.02);
                        border-radius: 16px;
                        padding: 20px;
                        border: 1px rgba(255, 255, 255, 0.04) solid;
                    }}
                    .qr-box {{
                        background: #fff;
                        padding: 10px;
                        border-radius: 12px;
                        display: inline-block;
                        margin-bottom: 15px;
                    }}
                    .qr-box img {{
                        width: 200px;
                        height: 200px;
                        display: block;
                    }}
                    .qr-info {{
                        font-size: 13px;
                        color: #a0a0b0;
                        line-height: 1.6;
                        text-align: left;
                    }}
                    .qr-info strong {{
                        color: #fff;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">XALA ECO CHECKOUT</div>
                    
                    <div class="bill-info">
                        <div class="bill-row">
                            <span class="label">Khách hàng:</span>
                            <span class="val">{payment.customer_id.name}</span>
                        </div>
                        <div class="bill-row">
                            <span class="label">Mã hóa đơn:</span>
                            <span class="val">#{payment.name}</span>
                        </div>
                        <div class="bill-row">
                            <span class="label">Kỳ thu phí:</span>
                            <span class="val">Tháng {payment.billing_id.month}/{payment.billing_id.year}</span>
                        </div>
                        <div class="bill-row">
                            <span class="label">Số tiền cần thanh toán:</span>
                            <span class="val price">{amount_fmt} VNĐ</span>
                        </div>
                    </div>

                    <div class="section-title">Chọn ví hoặc cổng thanh toán</div>
                    <div class="btn-list">
                        <a href="{base_url}/payment/vnpay_direct/{payment.id}" class="pay-btn btn-vnpay">
                            Thanh toán qua Cổng VNPay
                        </a>
                        <a href="{base_url}/payment/momo_direct/{payment.id}" class="pay-btn btn-momo">
                            Thanh toán qua Ví MoMo
                        </a>
                    </div>
                </div>
            </body>
        </html>
        """
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html'),
            ('ngrok-skip-browser-warning', 'true')
        ])
