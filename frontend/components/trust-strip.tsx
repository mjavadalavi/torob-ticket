import { GuaranteeMark } from "./brand";

export function TrustStrip() {
  return (
    <section className="trust-strip page-shell" aria-label="مزایای بلیت ترب">
      <article><span className="trust-icon success"><img className="trust-generated-icon" src="/images/trust/reliable-choice-generated.png" alt="" /></span><div><h3>اطلاعات شفاف و قابل اعتماد</h3><p>انتخابی مطمئن برای سفر شما</p></div></article>
      <article><span className="trust-icon pay"><span className="trust-pay-crop"><img className="trust-pay-photo" src="/images/trust/torob-pay.png" alt="ترب‌پی" /></span></span><div><h3>ترب‌پی</h3><p>در پیشنهادهای دارای قابلیت پرداخت اعتباری</p></div></article>
      <article><span className="trust-icon guarantee"><GuaranteeMark /></span><div><h3>تضمین ترب</h3><p>فقط برای پیشنهادهای دارای نشان تضمین ترب</p></div></article>
      <article><span className="trust-icon search"><img className="trust-generated-icon" src="/images/trust/compare-prices-generated.png" alt="" /></span><div><h3>مقایسه سریع و آسان</h3><p>همه گزینه‌ها در یک نگاه</p></div></article>
    </section>
  );
}
