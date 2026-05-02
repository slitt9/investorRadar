type MarketStatus = {
  label: "Open" | "Closed";
  opensAt: string;
  closesAt: string;
  isOpen: boolean;
};

function getEasternParts(date: Date) {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = dtf.formatToParts(date);
  const weekday = parts.find((p) => p.type === "weekday")?.value ?? "Mon";
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? "0");
  return { weekday, hour, minute };
}

export function getUsMarketStatus(now = new Date()): MarketStatus {
  const { weekday, hour, minute } = getEasternParts(now);
  const isWeekend = weekday === "Sat" || weekday === "Sun";
  const minutes = hour * 60 + minute;
  const openMinutes = 9 * 60 + 30;
  const closeMinutes = 16 * 60;

  const isOpen = !isWeekend && minutes >= openMinutes && minutes < closeMinutes;
  return {
    label: isOpen ? "Open" : "Closed",
    opensAt: "9:30 AM ET",
    closesAt: "4:00 PM ET",
    isOpen,
  };
}

