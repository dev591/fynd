/** Razorpay Checkout in the browser (test mode). Same flow as the team's Razorpay project: load checkout.js, open it with the
 *  order id from our server, and hand back the three values the server needs to verify the payment. */
declare global { interface Window { Razorpay?: new (o: Record<string, unknown>) => { open: () => void; on: (e: string, cb: (r: { error?: { description?: string } }) => void) => void } } }

let loading: Promise<void> | null = null;

function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => { loading = null; reject(new Error("Could not load Razorpay. Check your connection and try again.")); };
    document.head.appendChild(s);
  });
  return loading;
}

export interface CheckoutResult { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }

export async function payWithRazorpay(o: { key: string; order_id: string; amount: number; name: string; description: string; email?: string }): Promise<CheckoutResult> {
  await loadCheckout();
  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: o.key, order_id: o.order_id, amount: o.amount, currency: "INR", name: o.name, description: o.description,
      prefill: o.email ? { email: o.email } : undefined, theme: { color: "#c8381a" },
      handler: (r: CheckoutResult) => resolve(r),
      modal: { ondismiss: () => reject(new Error("Payment cancelled. Nothing was charged.")) },
    });
    rzp.on("payment.failed", r => reject(new Error(r.error?.description || "Razorpay declined the payment. Nothing was charged.")));
    rzp.open();
  });
}
