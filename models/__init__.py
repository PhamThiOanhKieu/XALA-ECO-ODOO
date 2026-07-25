from . import customer
from . import contract
from . import billing
from . import payment
from . import dashboard
from . import hr_management
from . import customer_map
from . import feedback
from . import employee_map
from . import contract_map
from . import payment_map

from . import account_move
from . import res_company
from . import account_payment_register

from . import momo_utils
from . import sepay_utils


# Monkeypatch ir.actions.report to force using the packaged wkhtmltopdf on Windows
import os
import logging
from odoo.addons.base.models import ir_actions_report

_logger = logging.getLogger(__name__)

try:
    default_packaged_path = r"C:\Program Files\Odoo 19.0.20260307\thirdparty\wkhtmltopdf.exe"
    if os.path.exists(default_packaged_path):
        def new_wkhtml():
            return ir_actions_report.WkhtmlInfo(
                state='ok',
                dpi_zoom_ratio=True,
                bin=default_packaged_path,
                version='0.12.6',
                is_patched_qt=True,
                wkhtmltoimage_bin='',
                wkhtmltoimage_version=None
            )
        ir_actions_report._wkhtml = new_wkhtml
        _logger.info("Successfully monkeypatched wkhtmltopdf path to: %s", default_packaged_path)
except Exception as e:
    _logger.error("Failed to monkeypatch wkhtmltopdf: %s", e)