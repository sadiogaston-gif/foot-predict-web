import { COUNTRY_FLAGS } from "@/lib/leagues";

interface Props {
  country?: string | null;
  size?: number;
  className?: string;
}

/** Drapeau du pays (flagcdn). Ne rend rien si le pays est inconnu. */
export default function CountryFlag({ country, size = 16, className = "" }: Props) {
  const url = country ? COUNTRY_FLAGS[country] : undefined;
  if (!url) return null;
  return (
    <img
      src={url}
      alt=""
      aria-hidden="true"
      loading="lazy"
      className={`shrink-0 rounded-[2px] object-cover ${className}`}
      style={{ width: size, height: Math.round(size * 0.75) }}
    />
  );
}