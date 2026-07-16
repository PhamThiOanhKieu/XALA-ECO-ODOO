/** @odoo-module alias=XALA-ECO-ODOO.xalaeco_dashboard **/

import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";

class XalaEcoDashboard extends Component {
    setup() {
        this.powerBiUrl = "https://app.powerbi.com/reportEmbed?reportId=182fc8e4-a47d-45dc-b0c8-80a9eddac22b&autoAuth=true&ctid=14d5de2b-d212-4175-92d5-156ea5b7c037";
    }
}

XalaEcoDashboard.template = xml`
    <div class="o_action" style="background-color: #f9f9f9; padding: 16px; height: 100%; display: flex; flex-direction: column;">   
        <div style="flex-grow: 1; width: 100%; height: 750px; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <object t-att-data="powerBiUrl" type="text/html" style="width: 100%; height: 100%; border: none;">
                <p>Trình duyệt của bạn không hỗ trợ hiển thị bản nhúng này.</p>
            </object>
        </div>
    </div>
`;

// Đăng ký action vào hệ thống
registry.category("actions").add("xalaeco_dashboard_owl", XalaEcoDashboard);