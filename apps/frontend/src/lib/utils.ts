import { clsx } from "clsx";

export function cn(...parts: Array<string | false | null | undefined>) {
  return clsx(parts);
}

export function formatCurrency(value: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2
  }).format(value ?? 0);
}

export function formatQuantity(value: number, maximumFractionDigits = 4) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits
  }).format(value ?? 0);
}

export function formatPct(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}
