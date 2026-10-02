import { useState } from "react";

const STAR_PATH = "M10 1.6l2.6 5.3 5.8.8-4.2 4.1 1 5.8L10 14.9l-5.2 2.7 1-5.8L1.6 7.7l5.8-.8z";

export function StarIcon({ filled = true, size = 16 }: { filled?: boolean; size?: number }) {
  return (
    <svg className={filled ? "star star-filled" : "star"} width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <path d={STAR_PATH} />
    </svg>
  );
}

export function StarRow({ value, size = 16 }: { value: number; size?: number }) {
  return (
    <span className="star-row" aria-label={`${value} de 5 estrelas`}>
      {[1, 2, 3, 4, 5].map((star) => <StarIcon key={star} filled={star <= value} size={size} />)}
    </span>
  );
}

/** Five buttons rather than a slider: one click is one rating, and each button says what it does. */
export function StarInput({ value, onChange, disabled }: {
  value: number | null;
  onChange: (stars: number) => void;
  disabled?: boolean;
}) {
  const [preview, setPreview] = useState<number | null>(null);
  const shown = preview ?? value ?? 0;
  return (
    <div className="star-input" onPointerLeave={() => setPreview(null)}>
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          className="star-button"
          aria-label={`Dar ${star} ${star === 1 ? "estrela" : "estrelas"}`}
          aria-pressed={value === star}
          disabled={disabled}
          onPointerEnter={() => setPreview(star)}
          onFocus={() => setPreview(star)}
          onBlur={() => setPreview(null)}
          onClick={() => onChange(star)}
        >
          <StarIcon filled={star <= shown} size={30} />
        </button>
      ))}
    </div>
  );
}
