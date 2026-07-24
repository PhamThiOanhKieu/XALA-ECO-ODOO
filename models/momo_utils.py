# -*- coding: utf-8 -*-
import hmac
import hashlib
import json
import requests
import logging

_logger = logging.getLogger(__name__)

def build_payment_url(params, access_key, secret_key, endpoint):
    """
    Hàm tạo chữ ký số HMAC-SHA256 gửi yêu cầu thanh toán lên MoMo Sandbox.
    """
    try:
        # MoMo yêu cầu định dạng chuỗi thô (Raw Signature) theo thứ tự định nghĩa nghiêm ngặt:
        raw_signature = (
            "accessKey=" + access_key +
            "&amount=" + str(params.get('amount', '')) +
            "&extraData=" + params.get('extraData', '') +
            "&ipnUrl=" + params.get('ipnUrl', '') +
            "&orderId=" + params.get('orderId', '') +
            "&orderInfo=" + params.get('orderInfo', '') +
            "&partnerCode=" + params.get('partnerCode', '') +
            "&redirectUrl=" + params.get('redirectUrl', '') +
            "&requestId=" + params.get('requestId', '') +
            "&requestType=" + params.get('requestType', '')
        )

        _logger.info("MoMo Raw Signature for Send: %s", raw_signature)

        # Tính toán chữ ký số HMAC-SHA256
        h = hmac.new(bytes(secret_key, 'ascii'), bytes(raw_signature, 'ascii'), hashlib.sha256)
        signature = h.hexdigest()
        
        # Thêm chữ ký vào gói dữ liệu gửi đi
        params['signature'] = signature

        # Gửi request POST dạng JSON lên cổng MoMo
        data_json = json.dumps(params)
        headers = {'Content-Type': 'application/json'}
        
        _logger.info("MoMo Sending JSON Payload: %s", data_json)
        response = requests.post(endpoint, data=data_json, headers=headers, timeout=15)
        
        res_data = response.json()
        _logger.info("MoMo Response JSON: %s", res_data)
        
        # Trả về link payUrl từ response nếu thành công
        if res_data.get('resultCode') == 0:
            return res_data.get('payUrl')
        else:
            _logger.error("MoMo API Error: %s", res_data.get('message'))
            return None
    except Exception as e:
        _logger.error("Exception in build_payment_url for MoMo: %s", e)
        return None

def verify_signature(params, secret_key):
    """
    Hàm đối soát chữ ký bảo mật HMAC-SHA256 nhận từ máy chủ MoMo trả về.
    """
    try:
        received_signature = params.get('signature')
        if not received_signature:
            return False

        # Các trường trả về của MoMo khi IPN/Return được sắp xếp bảng chữ cái để tạo chữ ký đối soát:
        raw_signature = (
            "accessKey=" + params.get('accessKey', '') +
            "&amount=" + str(params.get('amount', '')) +
            "&extraData=" + params.get('extraData', '') +
            "&message=" + params.get('message', '') +
            "&orderId=" + params.get('orderId', '') +
            "&orderInfo=" + params.get('orderInfo', '') +
            "&orderType=" + params.get('orderType', '') +
            "&partnerCode=" + params.get('partnerCode', '') +
            "&payType=" + params.get('payType', '') +
            "&requestId=" + params.get('requestId', '') +
            "&responseTime=" + str(params.get('responseTime', '')) +
            "&resultCode=" + str(params.get('resultCode', '')) +
            "&transId=" + str(params.get('transId', ''))
        )

        _logger.info("MoMo Raw Signature for Return: %s", raw_signature)

        # Tính toán mã băm cục bộ để so sánh
        h = hmac.new(bytes(secret_key, 'ascii'), bytes(raw_signature, 'ascii'), hashlib.sha256)
        calculated_signature = h.hexdigest()

        _logger.info("MoMo Signatures: Calculated=%s, Received=%s", calculated_signature, received_signature)
        return calculated_signature == received_signature
    except Exception as e:
        _logger.error("Exception in verify_signature for MoMo: %s", e)
        return False
