/**
 * Character asset map — keyed by agent slug.
 *
 * The AI team is represented by original human characters drawn in one comic
 * ink style. All ten characters use generated WebP artwork. SVG definitions remain as fallbacks.
 *
 * To swap in finished artwork later, set `image` on an entry:
 *
 *     CHARACTERS.study.image = "/art/study.png";
 *
 * Nothing in the layout depends on how a portrait is produced, so replacing one
 * is a one-line change. Artwork must contain no baked-in interface text — names
 * and roles are always rendered as HTML.
 */
import type { HairStyle, PropKind } from "@/components/art/Portrait";

export interface PortraitSpec {
  uid: string;
  /* skin */
  skin: string;
  skinShade: string;
  /* hair */
  hair: string;
  hairShade: string;
  hairStyle: HairStyle;
  /* face geometry — this is what makes them different people */
  headW?: number; // half-width at the cheekbones (default 80)
  jawW?: number; // half-width at the jaw (default 68)
  chinY?: number; // chin baseline (default 312)
  eyeW?: number; // eye half-width (default 19)
  eye: string;
  expression: "warm" | "bright" | "calm";
  glasses?: boolean;
  facialHair?: "beard" | "stubble" | "moustache";
  /* wardrobe + world */
  cloth: string;
  clothShade: string;
  collar: "crew" | "shirt" | "plain";
  bg: string;
  prop: PropKind;
}

export interface CharacterAsset {
  /** Meaningful alt text for the illustration. */
  alt: string;
  /** Optional finished-artwork override; when set, the SVG engine is bypassed. */
  image?: string;
  imagePosition?: string;
  art: PortraitSpec;
}

const SKIN = {
  light: ["#F8D7BA", "#E3B08C"],
  fair: ["#F1C69D", "#D7A070"],
  olive: ["#E0A579", "#BD7E50"],
  tan: ["#C98A5C", "#A3673C"],
  brown: ["#A2623A", "#7D4724"],
  deep: ["#774324", "#562D16"],
} as const;

const HAIR = {
  black: ["#1D1A17", "#443A32"],
  darkBrown: ["#3A281C", "#5E442F"],
  auburn: ["#8E4A22", "#B06B39"],
  chestnut: ["#59361F", "#7E4F30"],
  blonde: ["#C08F3C", "#DEB463"],
  ink: ["#221F20", "#4A4340"],
} as const;

export const CHARACTERS: Record<string, CharacterAsset> = {
  modeer: {
    image: "/art/sunshine/modeer-hero.webp",
    imagePosition: "78% 25%",
    alt: "Modeer — a person with dark tousled hair and a warm, attentive smile",
    art: {
      uid: "modeer",
      skin: SKIN.fair[0],
      skinShade: SKIN.fair[1],
      hair: HAIR.ink[0],
      hairShade: HAIR.ink[1],
      hairStyle: "tousled",
      headW: 82,
      jawW: 73,
      chinY: 318,
      eyeW: 19,
      eye: "#3B2A1E",
      expression: "warm",
      facialHair: "stubble",
      cloth: "#2B3A55",
      clothShade: "#1E2A3E",
      collar: "shirt",
      bg: "var(--sun)",
      prop: "desk",
    },
  },
  study: {
    image: "/art/sunshine/study.webp",
    alt: "The Study specialist — a person with dark hair in a bun, bright and encouraging, among books",
    art: {
      uid: "study",
      skin: SKIN.olive[0],
      skinShade: SKIN.olive[1],
      hair: HAIR.black[0],
      hairShade: HAIR.black[1],
      hairStyle: "bun",
      headW: 74,
      jawW: 58,
      chinY: 306,
      eyeW: 20,
      eye: "#4A3220",
      expression: "bright",
      cloth: "#E8709A",
      clothShade: "#C9527C",
      collar: "crew",
      bg: "var(--sun)",
      prop: "books",
    },
  },
  career: {
    image: "/art/sunshine/career.webp",
    alt: "The Career specialist — a person with a short fade and glasses in a smart jacket, city behind",
    art: {
      uid: "career",
      skin: SKIN.deep[0],
      skinShade: SKIN.deep[1],
      hair: HAIR.black[0],
      hairShade: HAIR.black[1],
      hairStyle: "fade",
      headW: 84,
      jawW: 77,
      chinY: 320,
      eyeW: 19,
      eye: "#3A2618",
      expression: "warm",
      glasses: true,
      facialHair: "stubble",
      cloth: "#3D4650",
      clothShade: "#2A3138",
      collar: "shirt",
      bg: "var(--sun-pale)",
      prop: "city",
    },
  },
  research: {
    image: "/art/sunshine/research.webp",
    alt: "The Research specialist — a person with voluminous curly hair, thoughtful, beside a bookshelf",
    art: {
      uid: "research",
      skin: SKIN.light[0],
      skinShade: SKIN.light[1],
      hair: HAIR.auburn[0],
      hairShade: HAIR.auburn[1],
      hairStyle: "curls",
      headW: 75,
      jawW: 61,
      chinY: 308,
      eyeW: 19,
      eye: "#4A6B49",
      expression: "calm",
      cloth: "#3F7D5C",
      clothShade: "#2D5C43",
      collar: "crew",
      bg: "var(--sun)",
      prop: "shelf",
    },
  },
  writing: {
    image: "/art/sunshine/writing.webp",
    alt: "The Writing specialist — a person with glasses and a side parting at a desk of notes",
    art: {
      uid: "writing",
      skin: SKIN.olive[0],
      skinShade: SKIN.olive[1],
      hair: HAIR.black[0],
      hairShade: HAIR.black[1],
      hairStyle: "sidepart",
      headW: 78,
      jawW: 67,
      chinY: 314,
      eyeW: 18,
      eye: "#3B2A1E",
      expression: "bright",
      glasses: true,
      cloth: "#EFE3C8",
      clothShade: "#D4C39C",
      collar: "crew",
      bg: "var(--sun)",
      prop: "desk",
    },
  },
  travel: {
    image: "/art/sunshine/travel.webp",
    alt: "The Travel specialist — a person with long wavy hair at a cafe table with a map and camera",
    art: {
      uid: "travel",
      skin: SKIN.tan[0],
      skinShade: SKIN.tan[1],
      hair: HAIR.darkBrown[0],
      hairShade: HAIR.darkBrown[1],
      hairStyle: "longwave",
      headW: 75,
      jawW: 60,
      chinY: 308,
      eyeW: 20,
      eye: "#4A3220",
      expression: "bright",
      cloth: "#2F7F86",
      clothShade: "#215F66",
      collar: "crew",
      bg: "var(--sun-pale)",
      prop: "map",
    },
  },
  shopping: {
    image: "/art/sunshine/shopping.webp",
    alt: "The Shopping specialist — a person with cropped hair beside a set of shopping bags",
    art: {
      uid: "shopping",
      skin: SKIN.fair[0],
      skinShade: SKIN.fair[1],
      hair: HAIR.chestnut[0],
      hairShade: HAIR.chestnut[1],
      hairStyle: "crop",
      headW: 81,
      jawW: 71,
      chinY: 316,
      eyeW: 18,
      eye: "#5A3A22",
      expression: "warm",
      cloth: "#E0763B",
      clothShade: "#BB5A28",
      collar: "crew",
      bg: "var(--pink-pale)",
      prop: "bags",
    },
  },
  finance: {
    image: "/art/sunshine/finance.webp",
    alt: "The Finance specialist — a person with a neat bob with a calculator and budgeting notebook",
    art: {
      uid: "finance",
      skin: SKIN.light[0],
      skinShade: SKIN.light[1],
      hair: HAIR.blonde[0],
      hairShade: HAIR.blonde[1],
      hairStyle: "bob",
      headW: 76,
      jawW: 62,
      chinY: 308,
      eyeW: 19,
      eye: "#3E6480",
      expression: "calm",
      cloth: "#2F5D4A",
      clothShade: "#224536",
      collar: "shirt",
      bg: "var(--sun-pale)",
      prop: "coins",
    },
  },
  fitness: {
    image: "/art/sunshine/fitness.webp",
    alt: "The Fitness specialist — a person with a high ponytail beside dumbbells and a weight plate",
    art: {
      uid: "fitness",
      skin: SKIN.brown[0],
      skinShade: SKIN.brown[1],
      hair: HAIR.black[0],
      hairShade: HAIR.black[1],
      hairStyle: "ponytail",
      headW: 77,
      jawW: 63,
      chinY: 310,
      eyeW: 20,
      eye: "#3A2618",
      expression: "bright",
      cloth: "#D34141",
      clothShade: "#AC2E2E",
      collar: "crew",
      bg: "var(--pink-pale)",
      prop: "weights",
    },
  },
  email: {
    image: "/art/sunshine/email.webp",
    alt: "The Email specialist — a person with short coils at a laptop holding an envelope",
    art: {
      uid: "email",
      skin: SKIN.deep[0],
      skinShade: SKIN.deep[1],
      hair: HAIR.black[0],
      hairShade: HAIR.black[1],
      hairStyle: "coils",
      headW: 82,
      jawW: 74,
      chinY: 318,
      eyeW: 19,
      eye: "#3A2618",
      expression: "warm",
      cloth: "#6B4E9E",
      clothShade: "#523A7C",
      collar: "crew",
      bg: "var(--sun)",
      prop: "mail",
    },
  },
};

const FALLBACK: CharacterAsset = {
  alt: "A member of your AI team",
  art: {
    uid: "fallback",
    skin: SKIN.olive[0],
    skinShade: SKIN.olive[1],
    hair: HAIR.darkBrown[0],
    hairShade: HAIR.darkBrown[1],
    hairStyle: "crop",
    eye: "#4A3220",
    expression: "warm",
    cloth: "#8A8F97",
    clothShade: "#6E727A",
    collar: "crew",
    bg: "var(--sun-pale)",
    prop: "none",
  },
};

export function characterFor(slug: string): CharacterAsset {
  return CHARACTERS[slug] ?? FALLBACK;
}
