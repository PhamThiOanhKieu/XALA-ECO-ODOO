from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def action_create_payments(self):
        # Kiểm tra xem có phải đang thực hiện thanh toán cho hóa đơn khách hàng (out_invoice) không
        invoices = self.line_ids.move_id
        if invoices and any(inv.move_type == 'out_invoice' for inv in invoices):
            invoice = invoices[0]
            
            # Tìm xalaeco.payment liên kết với hóa đơn này
            xala_payment = self.env['xalaeco.payment'].sudo().search([
                ('invoice_id', '=', invoice.id)
            ], limit=1)
            
            if not xala_payment:
                # Tìm hoặc tạo bản ghi khách hàng XALA ECO
                customer = self.env['xalaeco.customer'].sudo().search([
                    ('partner_id', '=', invoice.partner_id.id)
                ], limit=1)
                if not customer:
                    customer = invoice.xalaeco_customer_id
                if not customer:
                    customer = self.env['xalaeco.customer'].sudo().create({
                        'name': invoice.partner_id.name,
                        'partner_id': invoice.partner_id.id,
                        'phone': invoice.partner_id.phone,
                        'email': invoice.partner_id.email,
                    })
                
                # Tạo mới xalaeco.payment liên kết
                xala_payment = self.env['xalaeco.payment'].sudo().create({
                    'customer_id': customer.id,
                    'invoice_id': invoice.id,
                    'amount_due': self.amount,
                    'amount_paid': 0,
                    'note': f"Tự động sinh từ hóa đơn {invoice.name}",
                })
            else:
                # Cập nhật lại số tiền nếu người dùng thay đổi trên wizard
                xala_payment.sudo().write({
                    'amount_due': self.amount
                })
                
            # Chuyển hướng người dùng sang trang thanh toán VNPay
            return xala_payment.action_pay_vnpay()
            
        # Nếu không phải hóa đơn khách hàng (ví dụ: hóa đơn nhà cung cấp), giữ nguyên luồng Odoo
        return super(AccountPaymentRegister, self).action_create_payments()
