{
    'name': 'XALA ECO Management',
    'version': '1.0',
    'summary': 'Quản lý khách hàng, hợp đồng, thanh toán QR và doanh thu cho XALA ECO',
    'category': 'Management',
    'author': 'Group 2',
    'depends': ['base', 'web', 'mail', 'account', 'account_payment'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron.xml',
        'data/dashboard_data.xml',
        'data/contract_cron.xml',
        #'data/xala_customers.csv',

        'views/customer_views.xml',
        'views/customer_templates.xml',
        'views/contract_views.xml',
        'views/billing_views.xml',
        'views/payment_views.xml',
        'views/hr_management_views.xml',
        'views/dashboard_views.xml',
        'views/dashboard_views2.xml',
        'views/employee_map_views.xml',

        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/report_invoice.xml',

        'views/mobile_templates.xml',
        'views/sepay_redirect.xml',
        'views/feedback_views.xml',

        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'XALA_ECO_ODOO/static/src/xalaeco_dashboard.js',
        ],
    },
    'installable': True,
    'application': True,
}