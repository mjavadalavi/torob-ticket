import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "بلیت ترب | مقایسه قیمت بلیت سفر",
  description: "مقایسه قیمت بلیت پرواز، قطار و اتوبوس از چندین فروشنده",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl" data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
