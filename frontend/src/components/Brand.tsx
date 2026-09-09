import Link from "next/link";

/** The Modeer wordmark: heavy brush lettering with a pink ink underline. */
export function Brand({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const text =
    size === "lg" ? "text-[34px]" : size === "sm" ? "text-[20px]" : "text-[26px]";
  const rule = size === "lg" ? "h-[7px]" : size === "sm" ? "h-[4px]" : "h-[5px]";

  return (
    <Link href="/" className="group inline-block leading-none" aria-label="Modeer — home">
      <span
        className={`wordmark block ${text} text-ink`}
        style={{ transform: "skewX(-7deg)" }}
      >
        MODEER
      </span>
      <svg
        viewBox="0 0 120 8"
        preserveAspectRatio="none"
        className={`mt-1 block w-[74%] ${rule}`}
        aria-hidden
      >
        <path
          d="M2,6 C30,1 74,1 118,4"
          fill="none"
          stroke="var(--pink)"
          strokeWidth="5"
          strokeLinecap="round"
        />
      </svg>
    </Link>
  );
}
