import random
from odoo import models, fields, api

class XalaEcoCustomer(models.Model):
    _inherit = 'xalaeco.customer'

    lat = fields.Float(string='Vĩ độ', digits=(10, 7), compute='_compute_coordinates', store=True, readonly=False)
    lng = fields.Float(string='Kinh độ', digits=(10, 7), compute='_compute_coordinates', store=True, readonly=False)

    name = fields.Char(string='Tên khách hàng', required=False)
    customer_code = fields.Char(string='Mã khách hàng', required=False)

    # Excel dataset import helper fields
    house_no = fields.Char(string='house_no')
    street = fields.Char(string='street')
    ward = fields.Char(string='ward')
    full_address = fields.Text(string='full_address')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = vals.get('customer_code') or 'Khách hàng mới'
            if not vals.get('customer_code'):
                # Auto generate customer code
                vals['customer_code'] = 'KH' + str(random.randint(10000, 99999))
        return super(XalaEcoCustomer, self).create(vals_list)


    @api.depends('district', 'name', 'area')
    def _compute_coordinates(self):
        area_coords = {
            'Tuyến Thủ Đức': (10.8222, 106.7722),
            'Tuyến Bình Thạnh': (10.8038, 106.6983),
            'Tuyến Huỳnh Tịnh Của - Trần Quốc Toản': (10.7882, 106.6825),
            'Tuyến Phan Xích Long - Nguyễn Kiệm': (10.7992, 106.6803),
            'Tuyến Tân Bình - Tân Phú': (10.7966, 106.6438),
            'Tuyến Quận 7 - Nhà Bè': (10.7275, 106.7203),
            'Tuyến Quận 8 - Bình Chánh': (10.7240, 106.6286),
            'Tuyến Hóc Môn - Quận 12': (10.8672, 106.6641),
            'Tuyến Nguyễn Trãi - Trần Hưng Đạo': (10.7591, 106.6809),
        }
        district_coords = {
            'quan_1': (10.7769, 106.7009),
            'quan_3': (10.7792, 106.6811),
            'quan_4': (10.7580, 106.7067),
            'quan_5': (10.7541, 106.6625),
            'quan_6': (10.7483, 106.6349),
            'quan_7': (10.7275, 106.7203),
            'quan_8': (10.7240, 106.6286),
            'quan_10': (10.7749, 106.6669),
            'quan_11': (10.7629, 106.6432),
            'quan_12': (10.8672, 106.6641),
            'binh_tan': (10.7758, 106.5867),
            'binh_thanh': (10.8038, 106.6983),
            'go_vap': (10.8388, 106.6663),
            'phu_nhuan': (10.7992, 106.6803),
            'tan_binh': (10.8016, 106.6508),
            'tan_phu': (10.7916, 106.6368),
            'thu_duc': (10.8222, 106.7722),
            'binh_chanh': (10.6875, 106.5938),
            'can_gio': (10.4908, 106.8797),
            'cu_chi': (10.9992, 106.4983),
            'hoc_mon': (10.8844, 106.5919),
            'nha_be': (10.6656, 106.7278),
        }
        for rec in self:
            if not rec.lat or not rec.lng:
                base = None
                if rec.area and rec.area in area_coords:
                    base = area_coords[rec.area]
                if not base:
                    base = district_coords.get(rec.district or 'quan_1', (10.7769, 106.7009))
                
                if isinstance(rec.id, int):
                    seed_val = rec.id
                else:
                    seed_val = hash(rec.name or rec.customer_code or 'new_cust')
                random.seed(seed_val)
                offset_lat = random.uniform(-0.015, 0.015)
                offset_lng = random.uniform(-0.015, 0.015)
                rec.lat = base[0] + offset_lat
                rec.lng = base[1] + offset_lng
            else:
                # Keep current value if loaded or written
                pass

    def write(self, vals):
        if 'area' in vals or 'district' in vals:
            vals['lat'] = False
            vals['lng'] = False
        return super(XalaEcoCustomer, self).write(vals)
