
{
    'name': 'XALA ECO Management',
    'version': '1.0',
    'summary': 'Quản lý khách hàng, hợp đồng, thanh toán QR và doanh thu cho XALA ECO',
    'category': 'Management',
    'author': 'Group 2',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_management_views.xml',
        'data/sequence.xml',
        'data/dashboard_data.xml',
        'data/contract_cron.xml',
        #'data/xala_customers.csv',
        'views/customer_views.xml',
        'views/contract_views.xml',
        'views/billing_views.xml',
        'views/payment_views.xml',
        'views/dashboard_views.xml',
        'views/employee_map_views.xml',
        'views/menu.xml',

        'views/mobile_templates.xml', 
        
            ],
    'installable': True,
    'application': True,
}
