/** @odoo-module alias=XALA-ECO-ODOO.xalaeco_dashboard **/

import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";

// ==========================================
// BÁO CÁO 1: Dashboard tổng quan (Giữ nguyên)
// ==========================================
class XalaEcoDashboard extends Component {
    setup() {
        this.powerBiUrl = "https://app.powerbi.com/reportEmbed?reportId=8fdcd28b-7cb9-48e3-b312-c67f0f608dab&autoAuth=true&ctid=14d5de2b-d212-4175-92d5-156ea5b7c037&pageName=3898b735dced26b6a1e0&navContentPaneEnabled=false";
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
// Đăng ký action 1
registry.category("actions").add("xalaeco_dashboard_owl", XalaEcoDashboard);


// ==========================================
// BÁO CÁO 2: Báo cáo doanh thu (Trang mới bạn muốn nhúng)
// ==========================================
class XalaEcoRevenueDashboard extends Component {
    setup() {
                this.powerBiUrl = "https://app.powerbi.com/reportEmbed?reportId=8fdcd28b-7cb9-48e3-b312-c67f0f608dab&autoAuth=true&ctid=14d5de2b-d212-4175-92d5-156ea5b7c037&pageName=754617426c462ce4e59e&navContentPaneEnabled=false";

    }
}
XalaEcoRevenueDashboard.template = xml`
    <div class="o_action" style="background-color: #f9f9f9; padding: 16px; height: 100%; display: flex; flex-direction: column;">   
        <div style="flex-grow: 1; width: 100%; height: 750px; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <object t-att-data="powerBiUrl" type="text/html" style="width: 100%; height: 100%; border: none;">
                <p>Trình duyệt của bạn không hỗ trợ hiển thị bản nhúng này.</p>
            </object>
        </div>
    </div>
`;
// Đăng ký action 2
registry.category("actions").add("xalaeco_revenue_dashboard_owl", XalaEcoRevenueDashboard);