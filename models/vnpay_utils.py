"""
VNPay utility functions - chuyển đổi từ vnpay-main/routes/order.js (Node.js) sang Python
Dùng cho module xala_eco_odoo
"""
import hashlib
import hmac
import urllib.parse


def sort_object(params, encode=True):
    sorted_params = {}
    for key in sorted(params.keys()):
        value = str(params[key])
        if encode:
            encoded_value = urllib.parse.quote_plus(value)
        else:
            encoded_value = value
        sorted_params[key] = encoded_value
    return sorted_params


def build_query_string(sorted_params):
    """
    Tương đương querystring.stringify(vnp_Params, { encode: false })
    Vì các value đã được encode sẵn ở sort_object(), ở đây chỉ nối lại bằng & và =
    """
    return '&'.join(f"{k}={v}" for k, v in sorted_params.items())


def create_secure_hash(params, secret_key, encode=True):
    sorted_params = sort_object(params, encode=encode)
    sign_data = build_query_string(sorted_params)
    secure_hash = hmac.new(
        secret_key.encode('utf-8'),
        sign_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    return secure_hash, sorted_params


def build_payment_url(vnp_params, secret_key, vnp_url):
    """
    Tương đương route POST /create_payment_url trong order.js
    Trả về full URL để redirect khách sang VNPay.

    vnp_params: dict các tham số vnp_* CHƯA có vnp_SecureHash
    """
    secure_hash, sorted_params = create_secure_hash(vnp_params, secret_key)
    query_string = build_query_string(sorted_params)
    full_url = f"{vnp_url}?{query_string}&vnp_SecureHash={secure_hash}"
    return full_url


def verify_return_params(query_params, secret_key):
    """
    Tương đương route GET /vnpay_return trong order.js
    query_params: dict toàn bộ query string VNPay redirect về (bao gồm vnp_SecureHash)

    Trả về True nếu chữ ký hợp lệ, False nếu không.
    """
    # Chỉ giữ lại các tham số bắt đầu bằng 'vnp_' để đối chiếu chữ ký
    params = {k: v for k, v in query_params.items() if k.startswith('vnp_')}
    secure_hash = params.pop('vnp_SecureHash', None)
    params.pop('vnp_SecureHashType', None)

    if not secure_hash:
        return False

    calculated_hash, _ = create_secure_hash(params, secret_key)
    return secure_hash == calculated_hash