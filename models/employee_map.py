from odoo import models, fields

class XalaEmployeeMap(models.TransientModel):
    _name = 'xala.employee.map'
    _description = 'Bản đồ Giám sát'

    name = fields.Char(string='Tên bản đồ', default='Bản đồ Giám sát Tuyến Thu Gom')
