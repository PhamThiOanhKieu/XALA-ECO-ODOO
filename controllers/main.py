# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date, timedelta
import base64
from datetime import datetime
import random
import json
import logging
_logger = logging.getLogger(__name__)

from odoo.addons.xala_eco_odoo.models import vnpay_utils

SIM_TARGETS = {}

class XalaMobileController(http.Controller):

    @http.route('/xala_mobile/login', type='http', auth='public', website=False, methods=['GET', 'POST'])
    def mobile_login(self, **post):
        error = False
        if request.httprequest.method == 'POST':
            ma_nv = post.get('ma_nv')
            password = post.get('password')
            employee = request.env['xala.employee'].sudo().search([
                ('login_account', '=', ma_nv), 
                ('password', '=', password),
                ('state', '=', 'active')
            ], limit=1)
            
            if employee:
                request.session['mobile_emp_id'] = employee.id
                return request.redirect('/xala_mobile/dashboard')
            else:
                error = "Sai Mã nhân viên hoặc Mật khẩu!"
        
        return request.render('xala_eco.mobile_login_template', {'error': error})

    @http.route('/xala_mobile/dashboard', type='http', auth='public', website=False)
    def mobile_dashboard(self, filter_date=None, **kw):
        emp_id = request.session.get('mobile_emp_id')
        if not emp_id:
            return request.redirect('/xala_mobile/login')
        
        employee = request.env['xala.employee'].sudo().browse(emp_id)
        if not filter_date:
            filter_date = date.today().strftime('%Y-%m-%d')
            
        work_histories = request.env['xala.work.history'].sudo().search([
            ('employee_code', '=', employee.employee_code),
            ('work_date', '=', filter_date),
            ('shift_status', 'in', ['draft', 'in_progress'])
        ])
        
        histories_data = []
        for history in work_histories:
            start_str = ''
            customer_locs = []
            
            # 1. LẤY ĐIỂM XANH (KHÁCH HÀNG)
            if history.route_id and hasattr(history.route_id, 'customer_ids'):
                for cust in history.route_id.customer_ids:
                    # Sửa 'latitude' thành 'lat' cho khớp với data model
                    if hasattr(cust, 'lat') and hasattr(cust, 'lng'):
                        customer_locs.append({
                            'name': cust.name or 'Khách hàng',
                            'lat': cust.lat,
                            'lng': cust.lng
                        })
            
            # 2. LẤY ĐIỂM ĐỎ (NHÂN VIÊN)
            emp_loc = None
            try:
                # Đã sửa current_employee thành employee để không bị lỗi undefined
                if 'xala.employee.map' in request.env:
                    emp_map = request.env['xala.employee.map'].sudo().search([('employee_id', '=', employee.id)], limit=1)
                    if emp_map:
                        # Nếu chỗ này báo lỗi thì đổi thành emp_map.lat và emp_map.lng nhé
                        emp_loc = {'lat': emp_map.latitude, 'lng': emp_map.longitude} 
            except Exception as e:
                emp_loc = None 
                
            # 3. XỬ LÝ THỜI GIAN
            if history.start_time:
                if isinstance(history.start_time, str):
                    try:
                        # Đã sửa snetart_time thành start_time
                        time_obj = datetime.strptime(history.start_time, '%Y-%m-%d %H:%M:%S')
                        local_time = time_obj + timedelta(hours=7)
                        start_str = local_time.strftime('%H:%M')
                    except ValueError:
                        start_str = history.start_time
                else:
                    local_time = history.start_time + timedelta(hours=7)
                    start_str = local_time.strftime('%H:%M')

            histories_data.append({
                'id': history.id,
                'route_name': history.route_name,
                'date_assigned': history.work_date,
                'shift_type_str': history.shift_code,
                'state': history.shift_status,
                'start_time_str': start_str,
                'customer_locations': customer_locs,
                'employee_location': emp_loc
            })
        
        return request.render('xala_eco.mobile_dashboard_template', {
            'employee': employee,
            'work_histories': histories_data,
            'current_date': filter_date
        })
    @http.route('/xala_mobile/submit_attendance', type='json', auth='public', methods=['POST'])
    def submit_attendance(self, history_id, action_type, lat_lng, image_base64):
        emp_id = request.session.get('mobile_emp_id')
        if not emp_id:
            return {'status': 'error', 'message': 'Hết phiên đăng nhập!'}
        
        history = request.env['xala.work.history'].sudo().browse(int(history_id))
        if not history.exists():
            return {'status': 'error', 'message': 'Không tìm thấy lịch sử ca làm việc!'}
        
        if image_base64 and ',' in image_base64:
            image_base64 = image_base64.split(',')[1]

        if action_type == 'check_in':
            history.sudo().write({
                'start_time': datetime.now(),
                'gps_check_in': lat_lng,
                'image_check_in': image_base64,
                'shift_status': 'in_progress'
            })
        elif action_type == 'check_out':
            history.sudo().write({
                'end_time': datetime.now(),
                'gps_check_out': lat_lng,
                'image_check_out': image_base64,
                'shift_status': 'completed'
            })
            
        return {'status': 'success', 'message': 'Chấm công thành công!'}
    
    @http.route('/xala_mobile/logout', type='http', auth='public', website=True)
    def mobile_logout(self):
        """Hàm xử lý đăng xuất: Xóa phiên đăng nhập của nhân viên 
        và đá người dùng quay trở lại trang đăng nhập"""
        
        if 'mobile_emp_id' in request.session:
            request.session.pop('mobile_emp_id')
            
        return request.redirect('/xala_mobile/login')

    @http.route('/xala_eco/map_view', type='http', auth='user', website=False)
    def live_map_view(self, **kwargs):
        # BẮT TÍN HIỆU TỪ MOBILE TẠI ĐÂY
        is_mobile = kwargs.get('is_mobile', '0')
        emp_code = kwargs.get('emp_code', '')

        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Xala Eco - Bản đồ Giám sát Thu gom Rác</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: 'Inter', sans-serif;
            background: #f8fafc;
            overflow: hidden;
        }
        #map {
            width: 100%;
            height: 100%;
            z-index: 1;
        }
        /* Floating Control Panel */
        .control-panel {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            width: 320px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 12px;
            margin-bottom: 15px;
        }
        .panel-title {
            font-size: 16px;
            font-weight: 700;
            color: #0f172a;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .badge-live {
            background: #ef4444;
            color: white;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            animation: blink 1.5s infinite;
        }
        @keyframes blink {
            0% { opacity: 0.4; }
            50% { opacity: 1; }
            100% { opacity: 0.4; }
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }
        .stat-card {
            background: #f1f5f9;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        .stat-val {
            font-size: 20px;
            font-weight: 700;
            color: #1e293b;
        }
        .stat-label {
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
            font-weight: 500;
        }
        .legend-section {
            margin-bottom: 15px;
        }
        .legend-title {
            font-size: 12px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 8px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            color: #334155;
            margin-bottom: 6px;
        }
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 3px rgba(0,0,0,0.3);
        }
        .color-emp { background: #ef4444; }
        .color-cust { background: #10b981; }

        .switch-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f8fafc;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            margin-bottom: 15px;
        }
        .switch-label {
            font-size: 13px;
            font-weight: 600;
            color: #334155;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }
        .switch input { 
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #cbd5e1;
            transition: .3s;
            border-radius: 24px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #4f46e5;
        }
        input:checked + .slider:before {
            transform: translateX(20px);
        }

        .emp-list-container {
            max-height: 150px;
            overflow-y: auto;
            border-top: 1px solid #e2e8f0;
            padding-top: 12px;
        }
        .emp-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            padding: 6px 0;
            border-bottom: 1px solid #f1f5f9;
        }
        .emp-name-tag {
            font-weight: 600;
            color: #1e293b;
        }
        .emp-time-tag {
            color: #94a3b8;
            font-size: 11px;
        }

        .emp-marker {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            width: 60px;
            height: 70px;
        }
        .emp-label {
            background: #ef4444;
            color: white;
            font-family: 'Inter', sans-serif;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            white-space: nowrap;
            position: absolute;
            top: -5px;
            box-shadow: 0 2px 6px rgba(239, 68, 68, 0.4);
            border: 1px solid #fee2e2;
            z-index: 10;
        }
        .emp-svg-pin {
            z-index: 5;
            filter: drop-shadow(0px 4px 6px rgba(0, 0, 0, 0.35));
            margin-bottom: 5px;
        }
        .emp-radar-ring {
            position: absolute;
            border: 2.5px solid #ef4444;
            border-radius: 50%;
            opacity: 0;
            z-index: 1;
            bottom: 2px;
            left: 50%;
            margin-left: -15px; 
            width: 30px;
            height: 10px; 
        }
        .ring-1 {
            animation: radar 2s infinite linear;
        }
        .ring-2 {
            animation: radar 2s infinite linear;
            animation-delay: 0.6s;
        }
        .ring-3 {
            animation: radar 2s infinite linear;
            animation-delay: 1.2s;
        }
        @keyframes radar {
            0% {
                transform: scale(0.3);
                opacity: 0.8;
            }
            100% {
                transform: scale(2.8);
                opacity: 0;
            }
        }
        .cust-marker {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .cust-dot {
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            border: 1.5px solid white;
            box-shadow: 0 0 3px rgba(0,0,0,0.3);
        }
        .custom-div-icon {
            background: none !important;
            border: none !important;
        }
        
        /* ĐIỂM CHÈN CSS ĐỂ ẨN BẢNG CONTROL KHI Ở TRÊN MOBILE */
        /* MOBILE_CSS_PLACEHOLDER */
    </style>
</head>
<body>

    <div class="control-panel">
        <div class="panel-header">
            <h3 class="panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-map-pin"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
                Giám sát Tuyến
            </h3>
            <span class="badge-live">LIVE</span>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-val" id="count-emp">0</div>
                <div class="stat-label">Nhân viên Live</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" id="count-cust">0</div>
                <div class="stat-label">Khách hàng</div>
            </div>
        </div>

        <div class="legend-section">
            <div class="legend-title">Chú giải</div>
            <div class="legend-item">
                <div class="legend-color color-emp"></div>
                <span>Nhân viên thu gom (Mã NV)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color color-cust"></div>
                <span>Hộ dân / Khách hàng</span>
            </div>
        </div>

        <div class="switch-container">
            <span class="switch-label">Mô phỏng di chuyển</span>
            <label class="switch">
                <input type="checkbox" id="sim-toggle" checked="checked">
                <span class="slider"></span>
            </label>
        </div>

        <div class="emp-list-container" id="emp-list">
            <!-- Dynamic employee items -->
        </div>
    </div>

    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // ĐIỂM CHÈN MÃ LỌC NHÂN VIÊN
        const urlParams = new URLSearchParams(window.location.search);
        var TARGET_EMP_CODE = urlParams.get('emp_code');
        
        var map = L.map('map', {
            zoomControl: false
        }).setView([10.785, 106.65], 13);

        L.control.zoom({
            position: 'bottomleft'
        }).addTo(map);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        var employeeMarkers = {};
        var employeePaths = {};
        var customerMarkers = {};
        var firstLoad = true;

        function updateMap() {
            var simToggle = document.getElementById('sim-toggle');
            var simulate = (simToggle && simToggle.checked) ? '1' : '0';
            
            fetch('/xala_eco/get_map_data?simulate=' + simulate)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('count-emp').innerText = data.employees.length;
                    document.getElementById('count-cust').innerText = data.customers.length;

                    // Update Customers (Green dots)
                    var bounds = L.latLngBounds();
                    var hasPoints = false;

                    data.customers.forEach(cust => {
                        var lat = cust.lat;
                        var lng = cust.lng;
                        if (!lat || !lng) return;

                        var pos = [lat, lng];
                        bounds.extend(pos);
                        hasPoints = true;

                        if (customerMarkers[cust.id]) {
                            customerMarkers[cust.id].setLatLng(pos);
                        } else {
                            var custIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: `<div class="cust-marker"><div class="cust-dot"></div></div>`,
                                iconSize: [16, 16],
                                iconAnchor: [8, 8]
                            });

                            var marker = L.marker(pos, { icon: custIcon })
                                .bindPopup(`<strong>Khách hàng:</strong> ${cust.name}<br/><strong>Mã:</strong> ${cust.customer_code}<br/><strong>Tuyến:</strong> ${cust.area}`)
                                .addTo(map);
                            customerMarkers[cust.id] = marker;
                        }
                    });

                    // Update Employees (Red dots with codes)
                    var empListHtml = '';
                    data.employees.forEach(emp => {
                        // LỌC CỰC KỲ NGHIÊM NGẶT
                        var empMaNv = (emp.ma_nv || "").toString().trim().toLowerCase();
                        var targetCode = (TARGET_EMP_CODE || "").toString().trim().toLowerCase();

                        if (targetCode && targetCode !== empMaNv) {
                            return; // Loại ngay nếu không khớp
                        }

                        // Vẽ nhân viên sau khi đã lọc
                        var lat = emp.lat;
                        var lng = emp.lng;
                        if (!lat || !lng) return;

                        var pos = [lat, lng];
                        bounds.extend(pos);
                        hasPoints = true;

                        empListHtml += `
                            <div class="emp-item">
                                <span class="emp-name-tag">${emp.name} (${emp.ma_nv})</span>
                                <span class="emp-time-tag">${emp.last_update.split(' ')[1] || emp.last_update}</span>
                            </div>
                        `;

                        // Vẽ/Cập nhật đường di chuyển (trail) của nhân viên
                        var pathCoords = [];
                        if (emp.history && emp.history.length > 0) {
                            pathCoords = emp.history.map(pt => [pt[0], pt[1]]);
                        }
                        // Thêm tọa độ hiện tại nếu chưa có trong lịch sử
                        if (pathCoords.length === 0 || pathCoords[pathCoords.length - 1][0] !== lat || pathCoords[pathCoords.length - 1][1] !== lng) {
                            pathCoords.push(pos);
                        }

                        if (employeePaths[emp.id]) {
                            employeePaths[emp.id].setLatLngs(pathCoords);
                        } else {
                            employeePaths[emp.id] = L.polyline(pathCoords, {
                                color: '#ef4444',
                                weight: 4,
                                opacity: 0.75,
                                lineJoin: 'round',
                                dashArray: '8, 8'
                            }).addTo(map);
                        }

                        if (employeeMarkers[emp.id]) {
                            employeeMarkers[emp.id].setLatLng(pos);
                        } else {
                            var empIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: `<div class="emp-marker">
                                    <div class="emp-label">${emp.ma_nv}</div>
                                    <div class="emp-radar-ring ring-1"></div>
                                    <div class="emp-radar-ring ring-2"></div>
                                    <div class="emp-radar-ring ring-3"></div>
                                    <svg class="emp-svg-pin" width="30" height="42" viewBox="0 0 30 42" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M15 0C6.71573 0 0 6.71573 0 15C0 26.25 15 42 15 42C15 42 30 26.25 30 15C30 6.71573 23.2843 0 15 0ZM15 20.625C11.8934 20.625 9.375 18.1066 9.375 15C9.375 11.8934 11.8934 9.375 15 9.375C18.1066 9.375 20.625 11.8934 20.625 15C20.625 18.1066 18.1066 20.625 15 20.625Z" fill="url(#pinGrad)"/>
                                        <defs>
                                            <radialGradient id="pinGrad" cx="50%" cy="30%" r="50%">
                                                <stop offset="0%" stop-color="#ff6b6b"/>
                                                <stop offset="60%" stop-color="#ef4444"/>
                                                <stop offset="100%" stop-color="#b91c1c"/>
                                            </radialGradient>
                                        </defs>
                                    </svg>
                                </div>`,
                                iconSize: [60, 70],
                                iconAnchor: [30, 67]
                            });

                            var marker = L.marker(pos, { icon: empIcon })
                                .bindPopup(`<strong>Nhân viên:</strong> ${emp.name}<br/><strong>Mã NV:</strong> ${emp.ma_nv}<br/><strong>Tuyến thu gom:</strong> ${emp.route_name}<br/><strong>Cập nhật:</strong> ${emp.last_update}`)
                                .addTo(map);
                            employeeMarkers[emp.id] = marker;
                        }
                    });

                    document.getElementById('emp-list').innerHTML = empListHtml || '<div style="color: #94a3b8; font-size:12px; text-align:center;">Không có nhân viên online</div>';

                    if (firstLoad && hasPoints) {
                        map.fitBounds(bounds, { padding: [50, 50] });
                        firstLoad = false;
                    }
                })
                .catch(err => console.error("Error fetching map data:", err));
        }

        updateMap();
        setInterval(updateMap, 4000);
    </script>
</body>
</html>"""

        # XỬ LÝ ẨN BẢNG VÀ LỌC NHÂN VIÊN TỰ ĐỘNG BẰNG PYTHON
        if is_mobile == '1':
            html_content = html_content.replace('/* MOBILE_CSS_PLACEHOLDER */', '.control-panel { display: none !important; }')
        
        if emp_code:
            html_content = html_content.replace('EMP_CODE_PLACEHOLDER', emp_code)

        return request.make_response(html_content, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/xala_eco/get_map_data', type='http', auth='user', methods=['GET'])
    def get_map_data(self, **kwargs):
        import json
        simulate = kwargs.get('simulate') == '1'
        
        # Load active customers
        customers_data = []
        customers = request.env['xalaeco.customer'].sudo().search([('state', '=', 'active')])
        for cust in customers:
            customers_data.append({
                'id': cust.id,
                'name': cust.name,
                'customer_code': cust.customer_code,
                'lat': cust.lat,
                'lng': cust.lng,
                'area': cust.area or ''
            })
            
        # Load active employees
        employees_data = []
        target_emp_code = request.params.get('emp_code')
        
        domain = [('state', '=', 'active')]
        # Nếu có mã, chỉ lọc đúng 1 người đó thôi!
        if target_emp_code:
            domain.append(('employee_code', '=', target_emp_code))
            
        employees = request.env['xala.employee'].sudo().search(domain)
        
        for emp in employees:
            lat = emp.current_lat
            lng = emp.current_lng
            
            # Find the employee's route
            route_name = emp.route_name
            if not route_name:
                today_str = date.today().strftime('%Y-%m-%d')
                history = request.env['xala.work.history'].sudo().search([
                    ('employee_code', '=', emp.employee_code),
                    ('work_date', '=', today_str)
                ], limit=1)
                if history and history.route_name:
                    route_name = history.route_name
                else:
                    history_any = request.env['xala.work.history'].sudo().search([
                        ('employee_code', '=', emp.employee_code)
                    ], order='id desc', limit=1)
                    if history_any and history_any.route_name:
                        route_name = history_any.route_name
            
            # Get valid customers on this route
            route_custs = []
            if route_name:
                route_custs = [c for c in customers if c.area == route_name and c.lat and c.lng]
            
            # Fallback if no customers on route
            if not route_custs:
                route_custs = [c for c in customers if c.lat and c.lng]
                
            # If no customers in DB, fallback to default coordinate
            if not route_custs:
                fallback_pts = [(10.785, 106.65)]
            else:
                route_custs.sort(key=lambda c: c.id)
                fallback_pts = [(c.lat, c.lng) for c in route_custs]
                
            # Auto initialize if empty
            if not lat or not lng:
                start_idx = emp.id % len(fallback_pts)
                lat, lng = fallback_pts[start_idx]
                # Add a tiny random offset to prevent overlapping
                lat += random.uniform(-0.0001, 0.0001)
                lng += random.uniform(-0.0001, 0.0001)
                emp.sudo().update_gps_location(lat, lng)
            elif simulate:
                # Move sequentially towards customer coordinates on route
                global SIM_TARGETS
                target_idx = SIM_TARGETS.get(emp.id, 0)
                if target_idx >= len(fallback_pts):
                    target_idx = 0
                    
                target_lat, target_lng = fallback_pts[target_idx]
                
                import math
                dist = math.sqrt((target_lat - lat)**2 + (target_lng - lng)**2)
                
                step_size = 0.0008  # Approx 80-90 meters per 4s update
                
                if dist <= step_size:
                    lat, lng = target_lat, target_lng
                    target_idx = (target_idx + 1) % len(fallback_pts)
                    SIM_TARGETS[emp.id] = target_idx
                else:
                    lat += (target_lat - lat) * (step_size / dist)
                    lng += (target_lng - lng) * (step_size / dist)
                    
                emp.sudo().update_gps_location(lat, lng)
                
            history_list = []
            if emp.location_history:
                try:
                    history_list = json.loads(emp.location_history)
                except Exception:
                    history_list = []

            route_name = emp.route_name
            if not route_name:
                today_str = date.today().strftime('%Y-%m-%d')
                history = request.env['xala.work.history'].sudo().search([
                    ('employee_code', '=', emp.employee_code),
                    ('work_date', '=', today_str)
                ], limit=1)
                if history and history.route_name:
                    route_name = history.route_name
                else:
                    history_any = request.env['xala.work.history'].sudo().search([
                        ('employee_code', '=', emp.employee_code)
                    ], order='id desc', limit=1)
                    if history_any and history_any.route_name:
                        route_name = history_any.route_name

            employees_data.append({
                'id': emp.id,
                'name': emp.employee_name,
                'ma_nv': emp.employee_code,
                'route_name': route_name or 'Chưa phân tuyến',
                'lat': lat,
                'lng': lng,
                'last_update': emp.last_gps_update.strftime('%Y-%m-%d %H:%M:%S') if emp.last_gps_update else 'Chưa có',
                'history': history_list
            })
            
        res = {
            'customers': customers_data,
            'employees': employees_data
        }
        return request.make_response(json.dumps(res), headers=[('Content-Type', 'application/json')])

    @http.route('/xala_mobile/update_gps', type='json', auth='public', methods=['POST'])
    def update_gps(self, **post):
        emp_id = request.session.get('mobile_emp_id')
        if not emp_id:
            return {'status': 'error', 'message': 'Hết phiên đăng nhập!'}
        
        employee = request.env['xala.employee'].sudo().browse(emp_id)
        if not employee.exists():
            return {'status': 'error', 'message': 'Không tìm thấy nhân viên!'}
            
        lat_lng = post.get('lat_lng')
        lat, lng = 0.0, 0.0
        try:
            if lat_lng:
                # Expecting format: "Vĩ độ: 10.7769, Kinh độ: 106.7009"
                s = lat_lng.replace("Vĩ độ:", "").replace("Kinh độ:", "").replace("Vi do:", "").replace("Kinh do:", "")
                parts = [p.strip() for p in s.split(",")]
                if len(parts) >= 2:
                    lat = float(parts[0])
                    lng = float(parts[1])
        except Exception:
            pass
            
        if lat and lng:
            employee.sudo().update_gps_location(lat, lng)
            return {'status': 'success', 'message': f'Đã cập nhật vị trí ({lat}, {lng})'}
        else:
            return {'status': 'error', 'message': 'Tọa độ không hợp lệ'}

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
                <!-- CHỈNH SỬA NGÀY 21/07/2026: Sửa link quay lại Odoo -->
                <a href="/odoo/action-93" 
                   style="background-color: #875A7B; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; font-size: 16px;">
                    Quay lại Odoo
                </a>
                <!-- --------Hết---------- -->
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