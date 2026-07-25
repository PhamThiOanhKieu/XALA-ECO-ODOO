# -*- coding: utf-8 -*-

import logging
from odoo import http, fields
from odoo.http import request
from datetime import date
from ..models import vnpay_utils

_logger = logging.getLogger(__name__)

class VNPayController(http.Controller):

    @http.route('/payment/vnpay_return', type='http', auth='public', website=False, csrf=False)
    def vnpay_return(self, **kwargs):
        _logger.info("VNPay return called with params: %s", kwargs)
        ICP = request.env['ir.config_parameter'].sudo()
        secret_key = ICP.get_param('xalaeco.vnp_hash_secret')

        is_valid = vnpay_utils.verify_return_params(kwargs, secret_key)
        response_code = kwargs.get('vnp_ResponseCode')
        txn_ref = kwargs.get('vnp_TxnRef')
        bank_txn_no = kwargs.get('vnp_BankTranNo') or kwargs.get('vnp_TransactionNo')

        if is_valid and response_code == '00':
            payment = request.env['xalaeco.payment'].sudo().search(
                [('vnp_txn_ref', '=', txn_ref)], limit=1
            )
            if payment:
                pay_amount = payment.amount_due or payment.debt_amount
                
                payment.sudo().write({
                    'amount_paid': pay_amount,
                    'payment_date': date.today(),
                    'payment_method': 'vnpay',
                    'bank_transaction_code': bank_txn_no or txn_ref,
                    'note': 'Đã thanh toán tự động qua VNPay.',
                })

                # Đồng bộ trạng thái thanh toán lên hóa đơn Odoo liên kết nếu có
                if payment.invoice_id and payment.invoice_id.state == 'posted' and payment.invoice_id.payment_state not in ('paid', 'in_payment'):
                    try:
                        invoice = payment.invoice_id
                        journal = request.env['account.journal'].sudo().search([
                            ('type', '=', 'bank'),
                            ('company_id', '=', invoice.company_id.id)
                        ], limit=1)

                        if journal:
                            payment_method_line = journal.inbound_payment_method_line_ids[0] if journal.inbound_payment_method_line_ids else False
                            odoo_payment = request.env['account.payment'].sudo().create({
                                'amount': pay_amount,
                                'payment_type': 'inbound',
                                'partner_type': 'customer',
                                'partner_id': invoice.partner_id.id,
                                'journal_id': journal.id,
                                'payment_method_line_id': payment_method_line.id if payment_method_line else False,
                                'ref': invoice.name,
                            })
                            odoo_payment.action_post()

                            invoice_line = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
                            payment_line = odoo_payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
                            if invoice_line and payment_line:
                                (invoice_line + payment_line).reconcile()
                    except Exception as e:
                        _logger.error("Failed to automatically register invoice payment in Odoo: %s", e)

            return request.make_response("""
                <html>
                    <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                        <h1 style="color: green;">Thanh toán VNPay thành công!</h1>
                        <a href="/odoo/action-156" style="background-color: #875A7B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Quay lại Odoo</a>
                    </body>
                </html>
            """, headers=[('Content-Type', 'text/html')])
        else:
            return request.make_response("""
                <html>
                    <body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
                        <h1 style="color: red;">Thanh toán VNPay thất bại!</h1>
                        <a href="/odoo/action-156" style="background-color: #875A7B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Quay lại Odoo</a>
                    </body>
                </html>
            """, headers=[('Content-Type', 'text/html')])