export type HairStyle = "side-part" | "receding" | "slick" | "short" | "bob";
export type PresidentProfile = {
  slug: string;
  skin: string;
  hair: HairStyle;
  hairColor: string;
  glasses?: boolean;
  feminine?: boolean;
  accent: string;
  outfit: "barong" | "suit" | "dress";
};

const profile = (
  slug: string,
  overrides: Partial<PresidentProfile> = {},
): PresidentProfile => ({
  slug,
  skin: "#d8a173",
  hair: "side-part",
  hairColor: "#18212a",
  accent: "#d49a13",
  outfit: "barong",
  ...overrides,
});

export const presidentProfiles: Record<string, PresidentProfile> =
  Object.fromEntries(
    [
      profile("emilio-aguinaldo", {
        hair: "short",
        outfit: "suit",
        accent: "#295c91",
      }),
      profile("manuel-l-quezon", {
        hair: "slick",
        outfit: "suit",
        accent: "#824d35",
      }),
      profile("jose-p-laurel", {
        hair: "receding",
        outfit: "suit",
        glasses: true,
        accent: "#5f7048",
      }),
      profile("sergio-osmena", {
        hair: "receding",
        outfit: "suit",
        glasses: true,
        accent: "#526d86",
      }),
      profile("manuel-roxas", {
        hair: "side-part",
        outfit: "suit",
        accent: "#845d44",
      }),
      profile("elpidio-quirino", {
        hair: "receding",
        outfit: "suit",
        glasses: true,
        accent: "#5f7183",
      }),
      profile("ramon-magsaysay", {
        hair: "side-part",
        outfit: "barong",
        accent: "#d49a13",
      }),
      profile("carlos-p-garcia", {
        hair: "receding",
        outfit: "barong",
        glasses: true,
        accent: "#6d563c",
      }),
      profile("diosdado-macapagal", {
        hair: "slick",
        outfit: "barong",
        accent: "#315f91",
      }),
      profile("ferdinand-marcos", {
        hair: "side-part",
        outfit: "barong",
        accent: "#8c3d32",
      }),
      profile("corazon-aquino", {
        hair: "bob",
        outfit: "dress",
        feminine: true,
        glasses: true,
        accent: "#e0b51c",
      }),
      profile("fidel-v-ramos", {
        hair: "receding",
        outfit: "barong",
        glasses: true,
        accent: "#47725d",
      }),
      profile("joseph-estrada", {
        hair: "slick",
        outfit: "barong",
        accent: "#9b493c",
      }),
      profile("gloria-macapagal-arroyo", {
        hair: "bob",
        outfit: "dress",
        feminine: true,
        glasses: true,
        accent: "#50628d",
      }),
      profile("benigno-aquino-iii", {
        hair: "receding",
        outfit: "barong",
        glasses: true,
        accent: "#e0b51c",
      }),
      profile("rodrigo-duterte", {
        hair: "receding",
        outfit: "barong",
        accent: "#793f37",
      }),
      profile("bongbong-marcos", {
        hair: "side-part",
        outfit: "barong",
        accent: "#b03b34",
      }),
    ].map((value) => [value.slug, value]),
  );

export const presidentProfileOrder = [
  "emilio-aguinaldo",
  "manuel-l-quezon",
  "jose-p-laurel",
  "sergio-osmena",
  "manuel-roxas",
  "elpidio-quirino",
  "ramon-magsaysay",
  "carlos-p-garcia",
  "diosdado-macapagal",
  "ferdinand-marcos",
  "corazon-aquino",
  "fidel-v-ramos",
  "joseph-estrada",
  "gloria-macapagal-arroyo",
  "benigno-aquino-iii",
  "rodrigo-duterte",
  "bongbong-marcos",
];
