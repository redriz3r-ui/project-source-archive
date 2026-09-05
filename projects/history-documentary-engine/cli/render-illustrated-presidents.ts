import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

const slugs = [
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
const outputDir = path.resolve("../outputs/illustrated-presidents");
mkdirSync(outputDir, { recursive: true });
const force = process.argv.includes("--force");

const render = (index: number) =>
  new Promise<void>((resolve, reject) => {
    const number = String(index + 1).padStart(2, "0"),
      output = path.join(outputDir, `${number}-${slugs[index]}-segment.mp4`);
    if (!force && existsSync(output)) {
      console.log(`SKIP ${number} ${slugs[index]}`);
      resolve();
      return;
    }
    console.log(`START ${number} ${slugs[index]}`);
    const child = spawn(
      path.resolve("node_modules/.bin/remotion"),
      [
        "render",
        "src/index.ts",
        `IllustratedPresident${number}`,
        output,
        "--codec=h264",
        "--log=error",
      ],
      { stdio: "inherit" },
    );
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0
        ? (console.log(`DONE  ${number} ${slugs[index]}`), resolve())
        : reject(new Error(`${slugs[index]} render exited ${code}`)),
    );
  });

const main = async () => {
  let next = 0;
  const worker = async () => {
    while (next < slugs.length) {
      const index = next++;
      await render(index);
    }
  };
  await Promise.all([worker(), worker()]);
  console.log(`COMPLETE ${slugs.length} illustrated president chapters`);
};

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
