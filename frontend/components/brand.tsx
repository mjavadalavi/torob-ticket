export function TorobLogo() {
  return (
    <span className="brand" aria-label="ترب">
      <span className="brand-mark" aria-hidden="true"><span /></span>
      <span className="brand-word">ترب</span>
    </span>
  );
}

export function GuaranteeMark({ compact = false }: { compact?: boolean }) {
  return <span className={`guarantee-mark ${compact ? "compact" : ""}`} aria-hidden="true"><img src="/images/trust/torob-guarantee-hologram.svg" alt="" /></span>;
}

export function TorobPay() {
  return <span className="torob-pay" aria-label="ترب‌پی"><img src="/images/trust/torob-pay.png" alt="" /></span>;
}
