import { FilterIcon } from "./icons";
import { localizeTravelValue, price, toFa } from "@/lib/content";
import { OfferGroup, TravelMode } from "@/lib/types";
import { operatorFilterLabel } from "./mode-details";

export function Filters({
  mode,
  offers,
  selectedOperators,
  refundableOnly,
  onToggleOperator,
  onToggleRefundable,
  onClear,
}: {
  mode: TravelMode;
  offers: OfferGroup[];
  selectedOperators: string[];
  refundableOnly: boolean;
  onToggleOperator: (operator: string) => void;
  onToggleRefundable: () => void;
  onClear: () => void;
}) {
  const operatorCounts = offers.reduce<Record<string, number>>((counts, offer) => {
    counts[offer.attributes.operator] = (counts[offer.attributes.operator] ?? 0) + 1;
    return counts;
  }, {});
  const operators = Object.entries(operatorCounts).sort(([left], [right]) =>
    left.localeCompare(right, "fa"),
  );
  const prices = offers.map((offer) => offer.lowest_price.amount);
  const minimumPrice = prices.length ? Math.min(...prices) : null;
  const maximumPrice = prices.length ? Math.max(...prices) : null;
  const hasActiveFilters = selectedOperators.length > 0 || refundableOnly;
  const operatorTitle = operatorFilterLabel(mode);

  return (
    <aside className="filters">
      <header>
        <h2><FilterIcon /> فیلترها</h2>
        <button type="button" disabled={!hasActiveFilters} onClick={onClear}>پاک کردن همه</button>
      </header>
      <FilterSection title={operatorTitle}>
        {operators.length > 0 ? operators.map(([operator, count]) => (
          <label className="check" key={operator}>
            <input
              type="checkbox"
              checked={selectedOperators.includes(operator)}
              onChange={() => onToggleOperator(operator)}
            />
            <span />
            {localizeTravelValue(operator)}
            <small>({toFa(count)})</small>
          </label>
        )) : <p className="filter-empty">پس از دریافت نتیجه، شرکت‌ها اینجا نمایش داده می‌شوند.</p>}
      </FilterSection>
      {minimumPrice != null && maximumPrice != null && (
        <FilterSection title="بازه قیمت زنده">
          <p className="filter-price">
            {minimumPrice === maximumPrice
              ? `${price(minimumPrice)} تومان`
              : `از ${price(minimumPrice)} تا ${price(maximumPrice)} تومان`}
          </p>
        </FilterSection>
      )}
      <FilterSection title="قوانین استرداد">
        <label className="check">
          <input type="checkbox" checked={refundableOnly} onChange={onToggleRefundable} />
          <span />
          فقط گزینه‌های دارای قوانین استرداد
        </label>
      </FilterSection>
    </aside>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="filter-section"><h3>{title}</h3>{children}</section>;
}
