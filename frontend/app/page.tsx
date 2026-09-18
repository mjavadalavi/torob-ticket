import { Header } from "@/components/header";
import { SearchForm } from "@/components/search-form";
import { TrustStrip } from "@/components/trust-strip";
import { TravelMode } from "@/lib/types";

function validMode(value?: string): TravelMode { return value === "train" || value === "bus" ? value : "flight"; }

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ mode?: string }> }) {
  const { mode: rawMode } = await searchParams;
  const mode = validMode(rawMode);
  return (
    <main className={`search-page mode-${mode}`}>
      <Header />
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy page-shell"><div><h1 id="hero-title">بلیت ترب</h1><h2>مقایسه قیمت بلیت سفر</h2><p>بلیت مورد نظرتان را جستجو کنید و ارزان‌ترین گزینه‌ها را از میان<br/>چندین فروشگاه و آژانس مسافرتی مقایسه کنید.</p></div></div>
      </section>
      <div className="search-overlay page-shell"><SearchForm key={mode} mode={mode} /></div>
      <TrustStrip />
    </main>
  );
}
