document.addEventListener("DOMContentLoaded", function () {

    /* =============================
       COPY
    ============================== */
    document.querySelectorAll(".copy-btn").forEach(btn => {
        btn.onclick = function () {
            let id = btn.dataset.copy;
            let targetEl = document.getElementById(id);
            if(targetEl) {
                let value = targetEl.innerText;
                navigator.clipboard.writeText(value);
                btn.innerHTML = "Đã copy";
                setTimeout(function(){
                    btn.innerHTML = "Copy";
                }, 1500);
            }
        }
    });

    /* =============================
       COUNTDOWN
    ============================== */
    let countdown = document.getElementById("countdown");
    if(countdown && countdown.dataset.expired){
        let expire = new Date(countdown.dataset.expired.replace(" ","T"));
        setInterval(function(){
            let now = new Date();
            let diff = expire - now;
            if(diff <= 0){
                countdown.innerHTML = "Hết hạn";
                return;
            }
            let h = Math.floor(diff / 1000 / 60 / 60);
            let m = Math.floor(diff / 1000 / 60) % 60;
            let s = Math.floor(diff / 1000) % 60;

            countdown.innerHTML = 
                String(h).padStart(2,'0') + ":" +
                String(m).padStart(2,'0') + ":" +
                String(s).padStart(2,'0');
        }, 1000);
    }

    /* =============================
       POLLING CHECK STATUS
    ============================== */
    let order = document.getElementById("order_code");
    if(order){
        let checkInterval = setInterval(function(){
            let orderCode = order.innerText.trim();
            if(!orderCode) return;

            fetch("/payment/sepay/status/" + orderCode)
            .then(r => r.json())
            .then(function(data){
                if(data.status === "Paid"){
                    clearInterval(checkInterval);
                    
                    let statusEl = document.getElementById("payment_status");
                    if(statusEl){
                        statusEl.className = "status success";
                        statusEl.innerHTML = "Đã thanh toán";
                    }

                    let successBox = document.getElementById("payment-success");
                    if(successBox){
                        successBox.style.display = "flex";
                    }

                    setTimeout(function(){
                        window.location = "/odoo/action-156";
                    }, 3000);
                }
            })
            .catch(err => console.log("Polling error:", err));
        }, 3000);
    }
});