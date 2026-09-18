import Link from "next/link";
import { SearchIcon, UserIcon } from "./icons";
import { TorobLogo } from "./brand";

const categories = ["موبایل و کالای دیجیتال", "لپ‌تاپ و کامپیوتر اداری", "لوازم خانگی", "مد و پوشاک", "زیبایی و بهداشت", "خودرو و سایر وسایل نقلیه", "فرهنگی هنری", "ورزش و تناسب اندام", "اسباب بازی و سرگرمی", "سایر دسته‌ها"];

export function Header({ compact = false }: { compact?: boolean }) {
  return (
    <header className={`site-header ${compact ? "compact" : ""}`}>
      <div className="header-main page-shell">
        <Link href="/" className="logo-link"><TorobLogo /></Link>
        <div className="global-search"><span>جستجوی کالا، برند یا دسته‌بندی...</span><SearchIcon /></div>
        {compact && <Link className="new-search" href="/"><SearchIcon size={20} /> جستجوی جدید</Link>}
        <button className="login" type="button" aria-label="ورود یا ثبت‌نام"><UserIcon size={21} /> <span>ورود / ثبت‌نام</span></button>
      </div>
      <nav className="categories page-shell" aria-label="دسته‌بندی اصلی">
        <Link className="ticket-nav" href="/">بلیت</Link>
        {!compact && categories.map((category) => <span key={category}>{category}</span>)}
      </nav>
    </header>
  );
}
