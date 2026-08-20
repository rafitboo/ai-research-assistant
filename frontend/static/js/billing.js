document.addEventListener('alpine:init', () => {
    Alpine.data('billingDashboard', () => ({
        isLoading: true,
        isCheckingOut: false,
        isCanceling: false, // NEW
        urlStatus: null,
        statusData: {
            tier: 'Free',
            expires_at: null,
            cancel_at_period_end: false,
            history: []
        },

        get headers() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${window.USER_TOKEN}`
            };
        },

        async init() {
            const params = new URLSearchParams(window.location.search);
            if (params.has('status')) {
                this.urlStatus = params.get('status');
                window.history.replaceState(null, null, window.location.pathname);
                setTimeout(() => this.urlStatus = null, 5000);
            }
            await this.fetchStatus();
        },

        async fetchStatus() {
            this.isLoading = true;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/billing/status`, { headers: this.headers });
                if (res.ok) {
                    this.statusData = await res.json();
                }
            } catch (err) {
                console.error("Failed to fetch billing status:", err);
            } finally {
                this.isLoading = false;
            }
        },

        async initiatePayment() {
            this.isCheckingOut = true;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/billing/initiate-payment`, { 
                    method: 'POST',
                    headers: this.headers 
                });

                if (res.ok) {
                    const data = await res.json();
                    window.location.href = data.gateway_url;
                } else {
                    const err = await res.json();
                    alert(`Gateway initialization failed: ${err.detail}`);
                    this.isCheckingOut = false;
                }
            } catch (err) {
                console.error("Checkout error:", err);
                alert("Failed to connect to the backend server.");
                this.isCheckingOut = false;
            }
        },

        // --- NEW: Cancel Subscription Function ---
        async cancelSubscription() {
            if (!confirm("Are you sure you want to cancel your Premium subscription? You will lose access to all AI features at the end of your billing cycle.")) {
                return;
            }
            
            this.isCanceling = true;
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/billing/cancel-subscription`, { 
                    method: 'POST',
                    headers: this.headers 
                });

                if (res.ok) {
                    // Instantly refresh the UI to show the warning message
                    await this.fetchStatus();
                } else {
                    const err = await res.json();
                    alert(`Cancellation failed: ${err.detail}`);
                }
            } catch (err) {
                console.error("Cancellation error:", err);
                alert("An error occurred while trying to cancel the subscription.");
            } finally {
                this.isCanceling = true; // Button disappears anyway, but keeping state clean
            }
        },

        downloadInvoice(txn) {
            const invoiceText = `
====================================================
               PAYMENT INVOICE
====================================================
Date            : ${txn.date}
Transaction Ref : ${txn.ref}
Status          : ${txn.status}

Billed To       : Premium AI Researcher Plan
Amount Paid     : $${txn.amount.toFixed(2)} ${txn.currency}

----------------------------------------------------
Thank you for using the AI Research Assistant!
====================================================
            `;

            const blob = new Blob([invoiceText], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `Invoice_${txn.ref}.txt`; 
            
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }
    }));
});