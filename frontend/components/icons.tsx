import { ImgHTMLAttributes, SVGProps } from "react";
import type { TravelMode } from "@/lib/types";

type Props = SVGProps<SVGSVGElement> & { size?: number };
const base = (size: number) => ({ width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true });

export function SearchIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg> }
export function UserIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/></svg> }
export function PinIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg> }
export function CalendarIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg> }
export function SwapIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="m7 7 3-3M7 7l3 3M7 7h10M17 17l-3-3M17 17l-3 3M17 17H7"/></svg> }
export function ChevronIcon({ size = 20, ...props }: Props) { return <svg {...base(size)} {...props}><path d="m8 10 4 4 4-4"/></svg> }
export function ClockIcon({ size = 22, ...props }: Props) { return <svg {...base(size)} {...props}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg> }
export function ShieldIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-5"/></svg> }
export function FilterIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M4 6h16M7 12h10M10 18h4"/></svg> }
export function ExternalIcon({ size = 18, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/></svg> }
export function ArrowIcon({ size = 20, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M19 12H5m5-5-5 5 5 5"/></svg> }
export function BagIcon({ size = 22, ...props }: Props) { return <svg {...base(size)} {...props}><rect x="5" y="7" width="14" height="14" rx="2"/><path d="M9 7V5a3 3 0 0 1 6 0v2M9 11v6M15 11v6"/></svg> }
export function HomeIcon({ size = 22, ...props }: Props) { return <svg {...base(size)} {...props}><path d="m3 11 9-8 9 8v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/></svg> }
export function FlightIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path fill="currentColor" stroke="none" d="m21.6 11.4-7.5-2.6V4.2a2.1 2.1 0 0 0-4.2 0v4.6l-7.5 2.6a1 1 0 0 0-.6.9v1.6l8.1-1.5v4.1l-2.1 1.8v1.3l4.2-1 4.2 1v-1.3l-2.1-1.8v-4.1l8.1 1.5v-1.6a1 1 0 0 0-.6-.9Z"/><path d="M9.9 20.8 12 20.3l2.1.5" stroke="currentColor" strokeWidth="1.3"/></svg> }
export function TrainIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M7 3h10a4 4 0 0 1 4 4v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V7a4 4 0 0 1 4-4Z"/><path d="M6 8h4v4H6zM14 8h4v4h-4zM4 15h16M7 18l-2 3M17 18l2 3M8 21h8"/></svg> }
export function BusIcon({ size = 24, ...props }: Props) { return <svg {...base(size)} {...props}><path d="M6 3h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Z"/><path d="M6 7h12v5H6zM4 15h16M7 19v2M17 19v2"/><circle cx="7.5" cy="15" r="1" fill="currentColor" stroke="none"/><circle cx="16.5" cy="15" r="1" fill="currentColor" stroke="none"/></svg> }

const modeIconAssets: Record<TravelMode, string> = {
  flight: "/images/icons/mode-flight-v2.png",
  train: "/images/icons/mode-train-v2.png",
  bus: "/images/icons/mode-bus-v2.png",
};

type ModeIconProps = Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "width" | "height"> & {
  mode: TravelMode;
  size?: number;
};

export function ModeIcon({ mode, size = 24, alt = "", ...props }: ModeIconProps) {
  return <img
    {...props}
    className={`mode-image-icon ${props.className ?? ""}`.trim()}
    src={modeIconAssets[mode]}
    alt={alt}
    width={size}
    height={size}
    draggable={false}
    aria-hidden={alt ? undefined : true}
  />;
}
