import a1 from "../../public/wiki-tests/emilio-aguinaldo/president-manifest.json";
import a2 from "../../public/wiki-tests/manuel-l-quezon/president-manifest.json";
import a3 from "../../public/wiki-tests/jose-p-laurel/president-manifest.json";
import a4 from "../../public/wiki-tests/sergio-osmena/president-manifest.json";
import a5 from "../../public/wiki-tests/manuel-roxas/president-manifest.json";
import a6 from "../../public/wiki-tests/elpidio-quirino/president-manifest.json";
import a7 from "../../public/wiki-tests/ramon-magsaysay/president-manifest.json";
import a8 from "../../public/wiki-tests/carlos-p-garcia/president-manifest.json";
import a9 from "../../public/wiki-tests/diosdado-macapagal/president-manifest.json";
import a10 from "../../public/wiki-tests/ferdinand-marcos/president-manifest.json";
import a11 from "../../public/wiki-tests/corazon-aquino/president-manifest.json";
import a12 from "../../public/wiki-tests/fidel-v-ramos/president-manifest.json";
import a13 from "../../public/wiki-tests/joseph-estrada/president-manifest.json";
import a14 from "../../public/wiki-tests/gloria-macapagal-arroyo/president-manifest.json";
import a15 from "../../public/wiki-tests/benigno-aquino-iii/president-manifest.json";
import a16 from "../../public/wiki-tests/rodrigo-duterte/president-manifest.json";
import a17 from "../../public/wiki-tests/bongbong-marcos/president-manifest.json";
import { presidentSegmentSchema } from "../presidents/schema";

export const illustratedPresidentManifests = [
  a1,
  a2,
  a3,
  a4,
  a5,
  a6,
  a7,
  a8,
  a9,
  a10,
  a11,
  a12,
  a13,
  a14,
  a15,
  a16,
  a17,
].map((m) => presidentSegmentSchema.parse(m));
