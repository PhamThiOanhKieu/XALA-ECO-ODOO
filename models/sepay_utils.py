# -*- coding: utf-8 -*-

import requests

def create_order(api_key, bank_account_id, amount, tid, order_code):
    url = f"https://userapi-sandbox.sepay.vn/v2/bank-accounts/{bank_account_id}/orders"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount": amount,
        "tid": tid,
        "order_code": order_code,
        "with_qrcode": 1
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": True, "message": str(e)}