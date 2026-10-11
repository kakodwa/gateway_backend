import time
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
HTTP_TIMEOUT = (5, 15)

class PayChanguService:
    BASE_MOBILE_URL = "https://api.paychangu.com/mobile-money/payments/initialize"
    BASE_CARD_URL = "https://api.paychangu.com/hosted-payment-page"

    OPERATORS = {
        "airtel_money": {
            "prefixes": ("099", "098", "99", "98"),
            "id": "20be6c20-adeb-4b5b-a7ba-0769820df4fb",
            "name": "Airtel Money",
        },
        "tnm_mpamba": {
            "prefixes": ("088", "089", "88", "89"),
            "id": "27494cb5-ba9e-437f-a114-4e7a7686bcca",
            "name": "TNM Mpamba",
        }
    }

    def _headers(self):
        return {
            "Authorization": f"Bearer {settings.PAYCHANGU_SECRET_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _normalize_phone(self, phone: str):
        clean_phone = str(phone).strip().replace(" ", "").replace("+", "")
        if clean_phone.startswith("265"):
            clean_phone = clean_phone[3:]
        if not clean_phone.startswith("0"):
            clean_phone = f"0{clean_phone}"

        for key, op in self.OPERATORS.items():
            if any(clean_phone.startswith(prefix) for prefix in op["prefixes"]):
                return {
                    "phone": clean_phone,
                    "operator_id": op["id"],
                    "operator_name": op["name"]
                }
        raise ValueError("Unsupported mobile operator. Use Airtel or TNM.")

    def initiate_mobile_money(self, payment, phone_number):
        try:
            phone_data = self._normalize_phone(phone_number)
            payload = {
                "amount": float(payment.amount),
                "currency": "MWK",
                "mobile": phone_data["phone"],
                "mobile_money_operator_ref_id": phone_data["operator_id"],
                "charge_id": payment.payment_reference,
                "email": payment.user.email or "user@example.com",
            }
            res = requests.post(self.BASE_MOBILE_URL, json=payload, headers=self._headers(), timeout=HTTP_TIMEOUT)
            return self._handle_response(res)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def initiate_card_payment(self, payment, redirect_url=None):
        try:
            payload = {
                "public_key": getattr(settings, 'PAYCHANGU_PUBLIC_KEY', ''),
                "amount": float(payment.amount),
                "currency": "MWK",
                "email": payment.user.email or "user@example.com",
                "tx_ref": payment.payment_reference,
                "callback_url": redirect_url,
                "return_url": redirect_url,
            }
            res = requests.post(self.BASE_CARD_URL, json=payload, headers=self._headers(), timeout=HTTP_TIMEOUT)
            return self._handle_response(res)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_payment(self, charge_id):
        try:
            url = f"https://api.paychangu.com/mobile-money/payments/{charge_id}/verify"
            res = requests.get(url, headers=self._headers(), timeout=HTTP_TIMEOUT)
            return self._handle_response(res)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_response(self, response):
        try:
            data = response.json()
            if response.status_code in [200, 201]:
                return {"success": True, "data": data}
            return {"success": False, "status_code": response.status_code, "error": data}
        except Exception:
            return {"success": False, "error": "Invalid response"}