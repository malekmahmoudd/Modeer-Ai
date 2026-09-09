import Link from "next/link";

import { Icon } from "@/components/ui/Icon";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="group flex items-center gap-2.5">
      <span
        className="grid place-items-center rounded-[11px] text-white"
        style={{
          width: 32,
          height: 32,
          background: "linear-gradient(150deg, #8b7bff, #5b46d6)",
          boxShadow: "0 6px 20px -8px rgba(139,123,255,0.7)",
        }}
      >
        <Icon name="compass" size={18} />
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[13.5px] font-semibold tracking-tight text-white">
            Modeer
          </span>
          <span className="block text-[11px] text-content-faint">Personal AI team</span>
        </span>
      )}
    </Link>
  );
}
