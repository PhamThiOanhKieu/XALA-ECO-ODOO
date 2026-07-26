from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    xalaeco_tax_code = fields.Char(string='Mã số thuế đơn vị xuất (XALA ECO)', default='0311234567')
    xalaeco_bank_account = fields.Char(string='Số tài khoản nhận (XALA ECO)', default='1042253873')
    xalaeco_bank_name = fields.Char(string='Ngân hàng nhận (XALA ECO)', default='NH TMCP Ngoại thương Việt Nam (Vietcombank)')
    xalaeco_phone = fields.Char(string='SĐT đơn vị xuất (XALA ECO)', default='(0236) 3 999 888')
    xalaeco_email = fields.Char(string='Email đơn vị xuất (XALA ECO)', default='info@xalaeco.vn')
    xalaeco_address = fields.Text(string='Địa chỉ đơn vị xuất (XALA ECO)', default='123 Nguyễn Văn Linh, P. Phú Mỹ, Q.7, TP. Hồ Chí Minh')
    xalaeco_company_seal = fields.Binary(string='Con dấu/Chứng thực điện tử của Công ty')

    @api.model
    def _register_hook(self):
        super(ResCompany, self)._register_hook()
        companies = self.sudo().search([])
        if companies:
            companies.write({
                'xalaeco_tax_code': '0311234567',
                'xalaeco_address': '123 Nguyễn Văn Linh, P. Phú Mỹ, Q.7, TP. Hồ Chí Minh',
            })
            companies.filtered(lambda c: c.name == 'My Company').write({'name': 'CƠ SỞ KINH DOANH MTV XALA ECO'})
