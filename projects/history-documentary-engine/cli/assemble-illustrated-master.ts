import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const outputs = path.resolve("../outputs");
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
const clips = [
  "master-transitions/00-intro.mp4",
  ...slugs.flatMap((slug, index) => [
    ...(index
      ? [`master-transitions/${String(index).padStart(2, "0")}-move.mp4`]
      : []),
    `illustrated-presidents/${String(index + 1).padStart(2, "0")}-${slug}-segment.mp4`,
  ]),
  "master-transitions/17-outro.mp4",
];
const missing = clips.filter((clip) => !existsSync(path.join(outputs, clip)));
if (missing.length)
  throw new Error(`Missing master inputs:\n${missing.join("\n")}`);
const filters = clips.flatMap((_, index) => [
  `[${index}:v]setpts=PTS-STARTPTS,scale=1280:720,fps=30,format=yuv420p[v${index}]`,
  `[${index}:a]aresample=48000,asetpts=PTS-STARTPTS[a${index}]`,
]);
filters.push(
  `${clips.map((_, index) => `[v${index}][a${index}]`).join("")}concat=n=${clips.length}:v=1:a=1[vcat][acat]`,
);
filters.push("[acat]loudnorm=I=-16:LRA=11:TP=-1.5[aout]");
const output = path.join(
  outputs,
  "every-philippine-president-illustrated-rough-master.mp4",
);
const args = [
  "-y",
  "-v",
  "warning",
  ...clips.flatMap((clip) => ["-i", path.join(outputs, clip)]),
  "-filter_complex",
  filters.join(";"),
  "-map",
  "[vcat]",
  "-map",
  "[aout]",
  "-c:v",
  "libx264",
  "-preset",
  "veryfast",
  "-crf",
  "22",
  "-pix_fmt",
  "yuv420p",
  "-c:a",
  "aac",
  "-b:a",
  "160k",
  "-ar",
  "48000",
  "-ac",
  "2",
  "-movflags",
  "+faststart",
  output,
];
const child = spawn("/opt/homebrew/bin/ffmpeg", args, { stdio: "inherit" });
child.on("exit", (code) => {
  if (code === 0) console.log(`MASTER ${output}`);
  process.exitCode = code ?? 1;
});
