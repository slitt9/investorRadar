import type { LucideIcon } from "lucide-react";
import {
  Star,
  SlidersHorizontal,
  LineChart,
  Newspaper,
  BriefcaseBusiness,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  isPrimary?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "Watchlist", href: "/watchlist", icon: Star },
  { label: "Screener", href: "/screener", icon: SlidersHorizontal, isPrimary: true },
  { label: "Markets", href: "/markets", icon: LineChart },
  { label: "News", href: "/news", icon: Newspaper },
  { label: "Portfolio", href: "/portfolio", icon: BriefcaseBusiness },
];
