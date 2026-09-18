import Link from "next/link";
import { modeContent } from "@/lib/content";
import { TravelMode } from "@/lib/types";

export function ModeTabs({ mode }: { mode: TravelMode }) {
  return (
    <nav className="mode-tabs" aria-label="نوع بلیت">
      {(Object.keys(modeContent) as TravelMode[]).map((item) => (
        <Link href={`/?mode=${item}`} key={item} className={item === mode ? "active" : ""} aria-current={item === mode ? "page" : undefined}>
          {modeContent[item].label}
        </Link>
      ))}
    </nav>
  );
}
