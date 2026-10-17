interface MoneyProps {
  amount: number | null | undefined;
  className?: string;
  prefix?: string;
}

export function Money({ amount, className = "", prefix = "₹" }: MoneyProps) {
  if (amount === null || amount === undefined) {
    return <span className={`num text-muted ${className}`}>—</span>;
  }

  const formatted = Math.round(amount).toLocaleString("en-IN");

  return (
    <span className={`num font-mono tabular-nums ${className}`}>
      {prefix}
      {formatted}
    </span>
  );
}
