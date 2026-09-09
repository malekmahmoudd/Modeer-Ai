/**
 * Sunshine & Ink — comic portrait engine.
 *
 * Hand-authored SVG bust portraits: variable-weight ink contours, crosshatch
 * shading, halftone, warm comic colour. One shared drawing system with
 * per-character geometry (head width, jaw, hair, features, wardrobe, props) so
 * the cast reads as different people in a single illustration style.
 *
 * These are PROVISIONAL assets, drawn in code because this environment has no
 * image generator. `lib/characters.ts` maps agent slug -> spec and supports an
 * `image` override, so finished artwork can replace any portrait later without
 * touching layout.
 */
import type { PortraitSpec } from "@/lib/characters";

export type Framing = "bust" | "hero" | "panel" | "head";

const VIEWBOX: Record<Framing, string> = {
  bust: "0 0 400 500",
  hero: "66 58 268 442",
  panel: "34 52 332 392",
  head: "112 92 176 176",
};

export function Portrait({
  spec,
  alt,
  framing = "bust",
  className = "",
  decorative = false,
  transparent = false,
  fit = "cover",
}: {
  spec: PortraitSpec;
  alt: string;
  framing?: Framing;
  className?: string;
  decorative?: boolean;
  /** Drop the scene background so the page geometry shows through. */
  transparent?: boolean;
  /** "cover" crops to fill; "contain" fits the whole bust, bottom-anchored. */
  fit?: "cover" | "contain";
}) {
  const u = spec.uid;
  const { skin, skinShade, hair, hairShade, cloth, clothShade, bg, prop } = spec;

  const hw = spec.headW ?? 80; // half-width at the cheekbones
  const jw = spec.jawW ?? 68; // half-width at the jaw
  const chin = spec.chinY ?? 312;
  const hairScale = hw / 80;

  const head = headPath(hw, jw, chin);

  return (
    <svg
      viewBox={VIEWBOX[framing]}
      className={className}
      role={decorative ? "presentation" : "img"}
      aria-label={decorative ? undefined : alt}
      aria-hidden={decorative || undefined}
      preserveAspectRatio={fit === "contain" ? "xMidYMax meet" : "xMidYMid slice"}
    >
      <defs>
        <pattern
          id={`hatch-${u}`}
          width="8"
          height="8"
          patternTransform="rotate(40)"
          patternUnits="userSpaceOnUse"
        >
          <line x1="0" y1="0" x2="0" y2="8" stroke={skinShade} strokeWidth="2.6" />
        </pattern>
        <pattern id={`dots-${u}`} width="8" height="8" patternUnits="userSpaceOnUse">
          <circle cx="2.2" cy="2.2" r="1.7" fill="var(--ink)" opacity="0.55" />
        </pattern>
        <pattern id={`bgdots-${u}`} width="12" height="12" patternUnits="userSpaceOnUse">
          <circle cx="2.8" cy="2.8" r="2" fill="var(--ink)" opacity="0.11" />
        </pattern>
        <clipPath id={`head-${u}`}>
          <path d={head} />
        </clipPath>
        <clipPath id={`frame-${u}`}>
          <rect x="0" y="0" width="400" height="500" />
        </clipPath>
      </defs>

      <g clipPath={`url(#frame-${u})`}>
        {/* ---------- background ---------- */}
        {!transparent && (
          <>
            <rect x="0" y="0" width="400" height="500" fill={bg} />
            <path d="M0,0 L400,0 L400,132 L0,318 Z" fill="#fff" opacity="0.22" />
            <rect x="0" y="0" width="400" height="500" fill={`url(#bgdots-${u})`} />
            <Prop kind={prop} />
          </>
        )}

        {/* ---------- torso ---------- */}
        <g>
          <path d={BODY} fill={cloth} stroke="var(--ink)" strokeWidth="4.5" strokeLinejoin="round" />
          <path d={BODY_SHADE} fill={clothShade} opacity="0.95" />
          <path
            d={`M${200 - jw * 0.82},${chin + 56} C${200 - jw * 0.4},${chin + 86} ${200 + jw * 0.4},${chin + 86} ${200 + jw * 0.82},${chin + 56}`}
            fill="none"
            stroke="var(--ink)"
            strokeWidth="3.6"
            strokeLinecap="round"
          />
          {spec.collar === "shirt" && (
            <>
              <path
                d={`M${200 - jw * 0.62},${chin + 52} L200,${chin + 96} L${200 - jw * 0.18},${chin + 52} Z`}
                fill="#fdfaf0"
                stroke="var(--ink)"
                strokeWidth="3"
                strokeLinejoin="round"
              />
              <path
                d={`M${200 + jw * 0.62},${chin + 52} L200,${chin + 96} L${200 + jw * 0.18},${chin + 52} Z`}
                fill="#fdfaf0"
                stroke="var(--ink)"
                strokeWidth="3"
                strokeLinejoin="round"
              />
            </>
          )}
        </g>

        {/* ---------- neck ---------- */}
        <path
          d={`M${200 - jw * 0.44},${chin - 34} L${200 - jw * 0.44},${chin + 40} C${200 - jw * 0.44},${chin + 60} ${200 + jw * 0.44},${chin + 60} ${200 + jw * 0.44},${chin + 40} L${200 + jw * 0.44},${chin - 34} Z`}
          fill={skin}
          stroke="var(--ink)"
          strokeWidth="4"
          strokeLinejoin="round"
        />
        <path
          d={`M${200 - jw * 0.44},${chin - 30} C${200 - jw * 0.2},${chin + 14} ${200 + jw * 0.2},${chin + 14} ${200 + jw * 0.44},${chin - 30} L${200 + jw * 0.44},${chin - 34} L${200 - jw * 0.44},${chin - 34} Z`}
          fill={skinShade}
          opacity="0.9"
        />

        {/* ---------- hair behind ---------- */}
        <g transform={`translate(200,0) scale(${hairScale},1) translate(-200,0)`}>
          <HairBack style={spec.hairStyle} hair={hair} />
        </g>

        {/* ---------- head ---------- */}
        <path d={head} fill={skin} stroke="var(--ink)" strokeWidth="4.6" strokeLinejoin="round" />

        {/* form shading — terminator follows the face contour */}
        <g clipPath={`url(#head-${u})`}>
          <path
            d={`M${200 + hw * 0.06},90
                C${200 + hw * 0.46},132 ${200 + hw * 0.62},214 ${200 + jw * 0.46},${chin + 6}
                L${200 + hw + 12},${chin + 6} L${200 + hw + 12},90 Z`}
            fill={skinShade}
            opacity="0.6"
          />
          <path
            d={`M${200 + hw * 0.46},120
                C${200 + hw * 0.76},170 ${200 + hw * 0.8},240 ${200 + jw * 0.72},${chin}
                L${200 + hw + 12},${chin} L${200 + hw + 12},120 Z`}
            fill={`url(#hatch-${u})`}
            opacity="0.75"
          />
          <ellipse cx={200 - hw * 0.6} cy="250" rx="26" ry="15" fill={`url(#dots-${u})`} opacity="0.32" />
          <ellipse cx={200 + hw * 0.58} cy="252" rx="23" ry="14" fill={`url(#dots-${u})`} opacity="0.24" />
        </g>

        {/* ears */}
        <path
          d={`M${200 - hw + 2},198 C${200 - hw - 13},195 ${200 - hw - 18},211 ${200 - hw - 11},226 C${200 - hw - 7},235 ${200 - hw - 1},241 ${200 - hw + 4},241`}
          fill={skin}
          stroke="var(--ink)"
          strokeWidth="3.6"
          strokeLinecap="round"
        />
        <path
          d={`M${200 + hw - 2},198 C${200 + hw + 13},195 ${200 + hw + 18},211 ${200 + hw + 11},226 C${200 + hw + 7},235 ${200 + hw + 1},241 ${200 + hw - 4},241`}
          fill={skin}
          stroke="var(--ink)"
          strokeWidth="3.6"
          strokeLinecap="round"
        />

        {/* ---------- face ---------- */}
        <Face spec={spec} hw={hw} jw={jw} chin={chin} />

        {/* ---------- hair in front ---------- */}
        <g transform={`translate(200,0) scale(${hairScale},1) translate(-200,0)`}>
          <HairFront style={spec.hairStyle} hair={hair} shade={hairShade} />
        </g>

        {/* ---------- glasses ---------- */}
        {spec.glasses && <Glasses hw={hw} />}
      </g>
    </svg>
  );
}

/* ============================================================
   Geometry
   ============================================================ */

function headPath(hw: number, jw: number, chin: number) {
  const x = (d: number) => (200 + d).toFixed(1);
  return [
    `M200,96`,
    `C${x(hw * 0.7)},96 ${x(hw)},126 ${x(hw)},184`,
    `C${x(hw)},212 ${x(hw * 0.97)},238 ${x(jw * 1.08)},260`,
    `C${x(jw * 0.94)},${chin - 26} ${x(jw * 0.54)},${chin} 200,${chin}`,
    `C${x(-jw * 0.54)},${chin} ${x(-jw * 0.94)},${chin - 26} ${x(-jw * 1.08)},260`,
    `C${x(-hw * 0.97)},238 ${x(-hw)},212 ${x(-hw)},184`,
    `C${x(-hw)},126 ${x(-hw * 0.7)},96 200,96 Z`,
  ].join(" ");
}

const BODY =
  "M200,358 C242,358 288,378 308,410 C328,442 335,472 339,500 L61,500 C65,472 72,442 92,410 C112,378 158,358 200,358 Z";

const BODY_SHADE =
  "M230,368 C272,382 306,404 322,434 C332,456 336,478 339,500 L262,500 C260,454 250,406 230,368 Z";

/* ============================================================
   Face
   ============================================================ */

function Face({
  spec,
  hw,
  jw,
  chin,
}: {
  spec: PortraitSpec;
  hw: number;
  jw: number;
  chin: number;
}) {
  const { eye, expression, facialHair, skinShade } = spec;
  const ew = spec.eyeW ?? 19;
  const ex = hw * 0.4; // eye offset from centre
  const ey = 206;

  const bright = expression === "bright";
  const calm = expression === "calm";

  const browY = bright ? 176 : calm ? 183 : 180;
  const browLift = bright ? 13 : calm ? 6 : 10;

  const mouthW = jw * 0.46;
  const mouthDrop = bright ? 26 : expression === "warm" ? 18 : 11;
  const noseTip = 248;

  return (
    <g>
      {/* brows */}
      <path
        d={`M${200 - ex - ew},${browY + 4} Q${200 - ex},${browY - browLift} ${200 - ex + ew},${browY + 1}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="6.4"
        strokeLinecap="round"
      />
      <path
        d={`M${200 + ex - ew},${browY + 1} Q${200 + ex},${browY - browLift} ${200 + ex + ew},${browY + 4}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="6.4"
        strokeLinecap="round"
      />

      <Eye cx={200 - ex} cy={ey} w={ew} colour={eye} />
      <Eye cx={200 + ex} cy={ey} w={ew} colour={eye} />

      {/* nose */}
      <path
        d={`M203,218 C201,234 199,242 196,${noseTip - 1}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2.8"
        strokeLinecap="round"
        opacity="0.7"
      />
      <path
        d={`M${200 - 8},${noseTip} Q200,${noseTip + 7} ${200 + 10},${noseTip - 1}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />

      {/* mouth */}
      <path
        d={`M${200 - mouthW},${chin - 46} Q200,${chin - 46 + mouthDrop} ${200 + mouthW},${chin - 48}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      {bright && (
        <path
          d={`M${200 - mouthW + 5},${chin - 45} Q200,${chin - 45 + mouthDrop * 0.5} ${200 + mouthW - 5},${chin - 47} Q200,${chin - 43} ${200 - mouthW + 5},${chin - 45} Z`}
          fill="#fffdf6"
          opacity="0.92"
        />
      )}

      {/* smile creases */}
      <path
        d={`M${200 - jw * 0.62},${chin - 58} Q${200 - jw * 0.68},${chin - 44} ${200 - jw * 0.56},${chin - 34}`}
        fill="none"
        stroke={skinShade}
        strokeWidth="3.2"
        strokeLinecap="round"
        opacity="0.85"
      />
      <path
        d={`M${200 + jw * 0.62},${chin - 58} Q${200 + jw * 0.68},${chin - 44} ${200 + jw * 0.56},${chin - 34}`}
        fill="none"
        stroke={skinShade}
        strokeWidth="3.2"
        strokeLinecap="round"
        opacity="0.85"
      />
      {/* chin */}
      <path
        d={`M${200 - 15},${chin - 20} Q200,${chin - 13} ${200 + 15},${chin - 20}`}
        fill="none"
        stroke={skinShade}
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.7"
      />

      {facialHair === "beard" && (
        <path
          d={`M${200 - jw * 1.02},248 C${200 - jw * 0.98},${chin - 8} ${200 - jw * 0.5},${chin + 4} 200,${chin + 4}
              C${200 + jw * 0.5},${chin + 4} ${200 + jw * 0.98},${chin - 8} ${200 + jw * 1.02},248
              C${200 + jw * 0.86},${chin - 34} ${200 + jw * 0.44},${chin - 22} 200,${chin - 22}
              C${200 - jw * 0.44},${chin - 22} ${200 - jw * 0.86},${chin - 34} ${200 - jw * 1.02},248 Z`}
          fill="var(--ink)"
          opacity="0.86"
        />
      )}
      {facialHair === "stubble" && (
        <path
          d={`M${200 - jw * 0.98},258 C${200 - jw * 0.94},${chin - 4} ${200 - jw * 0.5},${chin + 2} 200,${chin + 2}
              C${200 + jw * 0.5},${chin + 2} ${200 + jw * 0.94},${chin - 4} ${200 + jw * 0.98},258
              C${200 + jw * 0.8},${chin - 30} ${200 + jw * 0.42},${chin - 18} 200,${chin - 18}
              C${200 - jw * 0.42},${chin - 18} ${200 - jw * 0.8},${chin - 30} ${200 - jw * 0.98},258 Z`}
          fill="var(--ink)"
          opacity="0.2"
        />
      )}
      {facialHair === "moustache" && (
        <path
          d={`M${200 - 25},${chin - 56} Q200,${chin - 64} ${200 + 25},${chin - 56} Q200,${chin - 50} ${200 - 25},${chin - 56} Z`}
          fill="var(--ink)"
          opacity="0.85"
        />
      )}
    </g>
  );
}

function Eye({ cx, cy, w, colour }: { cx: number; cy: number; w: number; colour: string }) {
  const h = w * 0.82;
  return (
    <g>
      <path
        d={`M${cx - w},${cy + 1} Q${cx - w * 0.1},${cy - h} ${cx + w},${cy - 2} Q${cx},${cy + h * 0.72} ${cx - w},${cy + 1} Z`}
        fill="#fffdf7"
      />
      <circle cx={cx + 1} cy={cy - 1} r={w * 0.4} fill={colour} />
      <circle cx={cx + 1} cy={cy - 1} r={w * 0.19} fill="var(--ink)" />
      <circle cx={cx + w * 0.22} cy={cy - w * 0.25} r={w * 0.12} fill="#fff" />
      <path
        d={`M${cx - w - 1},${cy + 1} Q${cx - w * 0.1},${cy - h - 2} ${cx + w + 1},${cy - 3}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="3.8"
        strokeLinecap="round"
      />
      <path
        d={`M${cx - w + 1},${cy + 2} Q${cx},${cy + h * 0.72} ${cx + w - 1},${cy - 1}`}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2.3"
        strokeLinecap="round"
        opacity="0.85"
      />
    </g>
  );
}

function Glasses({ hw }: { hw: number }) {
  const ex = hw * 0.4;
  const w = 56;
  const h = 33;
  const y = 191;
  return (
    <g fill="none" stroke="var(--ink)" strokeWidth="4.2" strokeLinejoin="round">
      <rect x={200 - ex - w / 2} y={y} width={w} height={h} rx="8" fill="#ffffff" opacity="0.16" />
      <rect x={200 - ex - w / 2} y={y} width={w} height={h} rx="8" />
      <rect x={200 + ex - w / 2} y={y} width={w} height={h} rx="8" fill="#ffffff" opacity="0.16" />
      <rect x={200 + ex - w / 2} y={y} width={w} height={h} rx="8" />
      <path d={`M${200 - ex + w / 2},${y + 11} L${200 + ex - w / 2},${y + 11}`} strokeWidth="4.4" />
      <path d={`M${200 - ex - w / 2},${y + 9} L${200 - hw - 4},${y + 16}`} strokeWidth="3.8" strokeLinecap="round" />
      <path d={`M${200 + ex + w / 2},${y + 9} L${200 + hw + 4},${y + 16}`} strokeWidth="3.8" strokeLinecap="round" />
    </g>
  );
}

/* ============================================================
   Hair
   ============================================================ */

export type HairStyle =
  | "tousled"
  | "bun"
  | "fade"
  | "curls"
  | "sidepart"
  | "longwave"
  | "bob"
  | "coils"
  | "ponytail"
  | "crop";

const INK = { stroke: "var(--ink)", strokeWidth: 4.2, strokeLinejoin: "round" as const };

function HairBack({ style, hair }: { style: HairStyle; hair: string }) {
  switch (style) {
    case "bun":
      return (
        <g fill={hair} {...INK}>
          <circle cx="200" cy="76" r="33" />
          <path d="M124,192 C116,138 152,88 200,88 C248,88 284,138 276,192 C272,150 246,120 200,120 C154,120 128,150 124,192 Z" />
        </g>
      );
    case "longwave":
      return (
        <g fill={hair} {...INK}>
          <path d="M112,182 C108,116 152,80 200,80 C248,80 292,116 288,182 C288,252 302,326 294,400 C270,374 262,320 262,266 C262,176 240,136 200,136 C160,136 138,176 138,266 C138,320 130,374 106,400 C98,326 112,252 112,182 Z" />
        </g>
      );
    case "bob":
      return (
        <g fill={hair} {...INK}>
          <path d="M114,190 C110,122 152,82 200,82 C248,82 290,122 286,190 C286,242 290,282 286,310 C266,300 256,268 256,220 C256,162 234,132 200,132 C166,132 144,162 144,220 C144,268 134,300 114,310 C110,282 114,242 114,190 Z" />
        </g>
      );
    case "ponytail":
      return (
        <g fill={hair} {...INK}>
          <path d="M266,132 C308,146 328,196 318,248 C310,290 290,318 272,324 C286,282 288,222 272,182 Z" />
          <path d="M124,188 C118,128 154,84 200,84 C246,84 282,128 276,188 C270,146 244,118 200,118 C156,118 130,146 124,188 Z" />
        </g>
      );
    case "curls":
      return (
        <g fill={hair} {...INK}>
          <path
            d="M108,244
               C98,208 108,176 124,154
               C126,120 152,94 182,90
               C196,78 214,78 228,92
               C258,98 276,124 278,154
               C294,176 302,208 292,244
               C302,274 290,304 268,310
               C280,276 276,242 270,212
               C264,156 238,126 200,126
               C162,126 136,156 130,212
               C124,242 120,276 132,310
               C110,304 98,274 108,244 Z"
          />
        </g>
      );
    case "coils":
      return (
        <g fill={hair} {...INK}>
          <path d="M122,178 C118,124 156,88 200,88 C244,88 282,124 278,178 C274,140 244,116 200,116 C156,116 126,140 122,178 Z" />
        </g>
      );
    case "tousled":
      return (
        <g fill={hair} {...INK}>
          <path d="M114,192 C108,118 150,74 202,74 C254,74 294,118 288,192 C286,226 290,248 284,266 C274,238 278,194 270,162 C258,114 232,98 200,98 C168,98 140,114 130,162 C122,194 126,238 116,266 C110,248 114,226 114,192 Z" />
        </g>
      );
    case "fade":
      return (
        <g fill={hair} {...INK}>
          <path d="M128,180 C126,142 158,112 200,112 C242,112 274,142 272,180 C266,154 242,138 200,138 C158,138 134,154 128,180 Z" />
        </g>
      );
    default:
      return (
        <g fill={hair} {...INK}>
          <path d="M122,188 C116,130 154,86 200,86 C246,86 284,130 278,188 C272,144 244,118 200,118 C156,118 128,144 122,188 Z" />
        </g>
      );
  }
}

function HairFront({ style, hair, shade }: { style: HairStyle; hair: string; shade: string }) {
  const strand = (d: string, key: number) => (
    <path key={key} d={d} fill="none" stroke={shade} strokeWidth="3.2" strokeLinecap="round" opacity="0.9" />
  );

  switch (style) {
    case "tousled":
      return (
        <g>
          <path
            d="M116,196 C112,126 150,90 202,90 C254,90 290,126 286,198 C272,180 268,150 244,136 C224,152 204,152 186,142 C170,160 148,152 136,168 C128,180 124,190 116,196 Z"
            fill={hair}
            {...INK}
          />
          {[
            "M142,134 C158,118 178,112 194,118",
            "M208,118 C226,114 246,124 256,140",
            "M132,164 C142,150 154,146 164,148",
            "M252,158 C262,168 268,182 268,194",
          ].map(strand)}
        </g>
      );
    case "bun":
      return (
        <g>
          <path
            d="M124,196 C120,136 154,96 200,96 C246,96 280,136 276,196 C266,174 258,144 234,132 C212,146 176,146 156,134 C138,148 132,176 124,196 Z"
            fill={hair}
            {...INK}
          />
          <path d="M140,200 C128,230 126,262 132,288" fill="none" stroke={hair} strokeWidth="8" strokeLinecap="round" />
          <path d="M260,200 C272,230 274,262 268,288" fill="none" stroke={hair} strokeWidth="8" strokeLinecap="round" />
          {["M156,124 C172,112 192,110 208,116"].map(strand)}
        </g>
      );
    case "fade":
      return (
        <g>
          <path
            d="M129,182 C127,144 158,116 200,116 C242,116 273,144 271,182 C262,162 246,148 200,148 C154,148 138,162 129,182 Z"
            fill={hair}
            {...INK}
          />
          {["M154,150 C174,140 200,137 224,142"].map(strand)}
        </g>
      );
    case "curls":
      return (
        <g>
          <path
            d="M124,192
               C120,164 126,140 140,126
               C150,110 172,100 196,100
               C220,100 244,110 256,126
               C272,140 280,164 276,192
               C266,176 258,156 240,146
               C222,158 178,158 160,146
               C142,156 134,176 124,192 Z"
            fill={hair}
            {...INK}
          />
          {/* curl texture, drawn inside the silhouette so the edge stays clean */}
          <g fill="none" stroke={shade} strokeWidth="3" strokeLinecap="round" opacity="0.9">
            <path d="M146,150 C154,134 168,126 182,126" />
            <path d="M196,120 C210,118 226,124 236,136" />
            <path d="M254,158 C262,170 266,182 266,192" />
            <path d="M136,172 C140,162 146,156 152,154" />
          </g>
        </g>
      );
    case "sidepart":
      return (
        <g>
          <path
            d="M124,192 C122,132 156,94 200,94 C248,94 282,132 280,192 C268,168 262,136 234,126 C208,144 174,138 158,130 C140,144 132,174 124,192 Z"
            fill={hair}
            {...INK}
          />
          <path d="M160,126 C186,112 222,114 240,130" fill="none" stroke={shade} strokeWidth="3.6" strokeLinecap="round" />
          {["M144,152 C154,138 168,130 184,130"].map(strand)}
        </g>
      );
    case "longwave":
      return (
        <g>
          <path
            d="M118,194 C116,126 152,90 200,90 C248,90 286,126 284,194 C270,172 262,138 236,128 C212,144 180,144 158,130 C136,146 128,176 118,194 Z"
            fill={hair}
            {...INK}
          />
          {[
            "M148,126 C166,112 190,108 210,114",
            "M228,120 C248,130 260,148 264,166",
          ].map(strand)}
        </g>
      );
    case "bob":
      return (
        <g>
          <path
            d="M118,194 C116,130 152,92 200,92 C248,92 284,130 282,194 C268,170 260,136 232,126 C210,142 178,142 158,128 C138,144 128,174 118,194 Z"
            fill={hair}
            {...INK}
          />
          {["M154,124 C178,110 208,110 230,122"].map(strand)}
        </g>
      );
    case "coils":
      return (
        <g>
          <path
            d="M126,188 C124,138 156,102 200,102 C244,102 276,138 274,188 C262,164 248,140 200,140 C152,140 138,164 126,188 Z"
            fill={hair}
            {...INK}
          />
          {[
            [148, 148],
            [174, 134],
            [200, 128],
            [226, 134],
            [252, 148],
            [134, 172],
            [266, 172],
            [162, 118],
            [238, 118],
          ].map(([cx, cy], i) => (
            <circle key={i} cx={cx} cy={cy} r="12" fill={hair} stroke="var(--ink)" strokeWidth="2.8" />
          ))}
        </g>
      );
    case "ponytail":
      return (
        <g>
          <path
            d="M124,192 C122,134 156,96 200,96 C244,96 278,134 276,192 C264,168 254,138 226,128 C204,144 178,142 162,130 C142,146 134,174 124,192 Z"
            fill={hair}
            {...INK}
          />
          {["M156,128 C180,114 210,114 230,126"].map(strand)}
        </g>
      );
    default: // crop
      return (
        <g>
          <path
            d="M126,190 C124,138 156,100 200,100 C244,100 276,138 274,190 C262,166 252,138 224,130 C202,146 176,144 160,132 C142,148 134,172 126,190 Z"
            fill={hair}
            {...INK}
          />
          {["M152,138 C176,124 204,122 224,132"].map(strand)}
        </g>
      );
  }
}

/* ============================================================
   Background props
   ============================================================ */

export type PropKind =
  | "books"
  | "city"
  | "shelf"
  | "desk"
  | "map"
  | "bags"
  | "coins"
  | "weights"
  | "mail"
  | "none";

function Prop({ kind }: { kind: PropKind }) {
  const ink = "var(--ink)";
  switch (kind) {
    case "books":
      return (
        <g stroke={ink} strokeWidth="3.6" strokeLinejoin="round">
          <rect x="10" y="356" width="92" height="24" fill="#fff" />
          <rect x="16" y="380" width="100" height="24" fill="var(--sun)" />
          <rect x="6" y="404" width="108" height="24" fill="var(--pink-pale)" />
          <rect x="292" y="372" width="94" height="24" fill="#fff" />
          <rect x="298" y="396" width="88" height="24" fill="var(--sun-pale)" />
          <rect x="286" y="420" width="100" height="24" fill="var(--pink-pale)" />
        </g>
      );
    case "city":
      return (
        <g stroke={ink} strokeWidth="3.2" fill="var(--navy)">
          <rect x="4" y="238" width="54" height="262" />
          <rect x="62" y="292" width="42" height="208" />
          <rect x="306" y="214" width="58" height="286" />
          <rect x="366" y="278" width="34" height="222" />
          <g fill="var(--sun)" stroke="none">
            {[254, 282, 310, 338, 366].map((y) => (
              <g key={y}>
                <rect x="16" y={y} width="13" height="13" />
                <rect x="37" y={y} width="13" height="13" />
                <rect x="318" y={y - 20} width="13" height="13" />
                <rect x="340" y={y - 20} width="13" height="13" />
              </g>
            ))}
          </g>
        </g>
      );
    case "shelf":
      return (
        <g stroke={ink} strokeWidth="3.4">
          <line x1="0" y1="188" x2="118" y2="188" />
          <rect x="8" y="136" width="18" height="52" fill="var(--pink-pale)" />
          <rect x="30" y="144" width="18" height="44" fill="#fff" />
          <rect x="52" y="130" width="18" height="58" fill="var(--sun)" />
          <rect x="74" y="148" width="18" height="40" fill="var(--navy)" />
          <line x1="0" y1="318" x2="96" y2="318" />
          <rect x="10" y="272" width="18" height="46" fill="var(--sun-pale)" />
          <rect x="32" y="264" width="18" height="54" fill="var(--pink-pale)" />
          <line x1="286" y1="170" x2="400" y2="170" />
          <rect x="298" y="120" width="18" height="50" fill="var(--sun-pale)" />
          <rect x="320" y="128" width="18" height="42" fill="#fff" />
          <rect x="342" y="116" width="18" height="54" fill="var(--pink-pale)" />
          <rect x="364" y="126" width="18" height="44" fill="var(--navy)" />
        </g>
      );
    case "desk":
      return (
        <g stroke={ink} strokeWidth="3.4">
          <rect x="6" y="382" width="116" height="82" rx="4" fill="#fdfaf0" />
          {[400, 416, 432, 448].map((y, i) => (
            <line key={y} x1="20" y1={y} x2={i % 2 ? 92 : 110} y2={y} strokeWidth="2.6" opacity="0.55" />
          ))}
          <rect x="300" y="396" width="70" height="68" rx="4" fill="var(--sun-pale)" />
          <line x1="318" y1="396" x2="318" y2="464" strokeWidth="2.6" opacity="0.55" />
          <path d="M340,396 L340,352" strokeWidth="4.4" strokeLinecap="round" />
          <circle cx="340" cy="346" r="7" fill="var(--pink)" />
        </g>
      );
    case "map":
      return (
        <g stroke={ink} strokeWidth="3.4">
          <rect x="6" y="122" width="116" height="92" rx="4" fill="#fdfaf0" />
          <path d="M18,186 C42,156 60,182 80,156 C98,134 110,154 116,142" fill="none" strokeWidth="3" />
          <circle cx="80" cy="156" r="8" fill="var(--pink)" />
          <path d="M300,112 L400,146" strokeWidth="3.2" strokeDasharray="10 9" fill="none" />
          <path d="M348,96 L378,126 L340,140 L332,116 Z" fill="#fff" />
        </g>
      );
    case "bags":
      return (
        <g stroke={ink} strokeWidth="3.6" strokeLinejoin="round">
          <rect x="8" y="390" width="80" height="90" rx="4" fill="var(--pink-pale)" />
          <path d="M30,390 C30,366 66,366 66,390" fill="none" />
          <rect x="94" y="416" width="62" height="64" rx="4" fill="var(--sun)" />
          <path d="M110,416 C110,396 140,396 140,416" fill="none" />
          <rect x="308" y="404" width="72" height="76" rx="4" fill="#fff" />
          <path d="M328,404 C328,382 360,382 360,404" fill="none" />
        </g>
      );
    case "coins":
      return (
        <g stroke={ink} strokeWidth="3.4">
          {[466, 446, 426, 406].map((y, i) => (
            <ellipse key={y} cx={54 + i * 2} cy={y} rx={42 - i * 3} ry="13" fill="var(--sun)" />
          ))}
          {[466, 446].map((y, i) => (
            <ellipse key={y} cx={344} cy={y} rx={36 - i * 3} ry="12" fill="var(--sun-deep)" />
          ))}
          <path d="M296,168 L326,214 L352,140 L382,186" fill="none" strokeWidth="4.6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      );
    case "weights":
      return (
        <g stroke={ink} strokeWidth="3.6" strokeLinejoin="round">
          <rect x="6" y="408" width="28" height="70" rx="5" fill="var(--navy)" />
          <rect x="38" y="426" width="20" height="34" rx="4" fill="var(--navy)" />
          <rect x="58" y="436" width="48" height="14" rx="5" fill="var(--ink)" />
          <rect x="106" y="426" width="20" height="34" rx="4" fill="var(--navy)" />
          <rect x="130" y="408" width="28" height="70" rx="5" fill="var(--navy)" />
          <circle cx="336" cy="418" r="38" fill="var(--sun)" />
          <circle cx="336" cy="418" r="12" fill="var(--paper)" />
        </g>
      );
    case "mail":
      return (
        <g stroke={ink} strokeWidth="3.6" strokeLinejoin="round">
          <rect x="6" y="392" width="104" height="72" rx="4" fill="#fff" />
          <path d="M6,392 L58,436 L110,392" fill="none" />
          <rect x="296" y="116" width="90" height="62" rx="4" fill="var(--sun-pale)" />
          <path d="M296,116 L341,155 L386,116" fill="none" />
          <path d="M256,228 C282,204 318,214 344,192" fill="none" strokeWidth="3.2" strokeDasharray="9 8" />
        </g>
      );
    default:
      return null;
  }
}
