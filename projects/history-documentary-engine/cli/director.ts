import {copyFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';

export const checkpointIds = [
  'TOPIC_PROMISE',
  'THESIS_ANGLE',
  'OPENING_HOOK',
  'STRUCTURE_TONE',
  'SCRIPT_STORYBOARD',
  'ROUGH_CUT',
  'FINAL_PUBLICATION',
] as const;

const choiceSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  consequence: z.string().min(1),
  recommended: z.boolean().default(false),
  topic: z.string().optional(),
  audiencePromise: z.string().optional(),
  evidenceUrls: z.array(z.string().url()).default([]),
});

const checkpointSchema = z.object({
  id: z.enum(checkpointIds),
  title: z.string().min(1),
  status: z.enum(['LOCKED', 'AWAITING_CHOICE', 'SELECTED']),
  options: z.array(choiceSchema).max(4),
  selectedOptionId: z.string().optional(),
  selectedAt: z.string().optional(),
});

export const directorStateSchema = z.object({
  schemaVersion: z.literal(1),
  projectId: z.string().min(1),
  houseStyle: z.literal('apollo-11-archive-opening'),
  status: z.enum(['DIRECTING', 'PRODUCING', 'COMPLETE']),
  activeCheckpoint: z.enum(checkpointIds),
  tokenTarget: z.literal(50_000),
  createdAt: z.string(),
  updatedAt: z.string(),
  checkpoints: z.array(checkpointSchema).length(7),
});

export type DirectorChoice = z.infer<typeof choiceSchema>;
export type DirectorState = z.infer<typeof directorStateSchema>;

export const episodeOneTopicOptions: DirectorChoice[] = [
  {
    id: 'tulsa-greenwood',
    label: 'Tulsa: What Greenwood Lost',
    consequence: 'Fastest route to launch: reuse the existing Tulsa research and archive work, then rebuild it to Apollo quality around what the destruction erased.',
    recommended: true,
    topic: 'The 1921 Tulsa Race Massacre and the destruction of Greenwood',
    audiencePromise: 'Show viewers what Greenwood had built, how it was destroyed, and why the loss was hidden for generations.',
    evidenceUrls: ['https://www.loc.gov/item/today-in-history/may-31/', 'https://www.loc.gov/pictures/item/2017679764/'],
  },
  {
    id: 'triangle-fire',
    label: 'Triangle: The Doors Were Locked',
    consequence: 'A contained, character-led tragedy with strong photographs and newspapers; visually rich, but requires fresh research and asset acquisition.',
    recommended: false,
    topic: 'The 1911 Triangle Shirtwaist Factory fire',
    audiencePromise: 'Reconstruct how ordinary working conditions turned one factory fire into a preventable catastrophe that changed labor law.',
    evidenceUrls: ['https://guides.loc.gov/this-month-in-business-history/march/triangle-shirtwaist-factory-fire', 'https://www.loc.gov/pictures/item/2003652928/'],
  },
  {
    id: 'blair-mountain',
    label: 'Blair Mountain: America’s Forgotten War',
    consequence: 'The most surprising and action-driven option, with a strong labor-conflict hook; archive sourcing will be harder and therefore slower.',
    recommended: false,
    topic: 'The 1921 Battle of Blair Mountain and the West Virginia Mine Wars',
    audiencePromise: 'Explain why thousands of armed miners marched across West Virginia and why the federal government intervened.',
    evidenceUrls: ['https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm', 'https://www.nps.gov/articles/000/introduction-to-the-west-virginia-mine-wars.htm'],
  },
];

const titles: Record<(typeof checkpointIds)[number], string> = {
  TOPIC_PROMISE: 'Topic and audience promise',
  THESIS_ANGLE: 'Historical thesis or narrative angle',
  OPENING_HOOK: 'Opening hook',
  STRUCTURE_TONE: 'Story structure and tone',
  SCRIPT_STORYBOARD: 'Script and archive storyboard approval',
  ROUGH_CUT: 'Rough-cut review',
  FINAL_PUBLICATION: 'Final publication approval',
};

export const createDirectorState = (projectId: string, now = new Date().toISOString()): DirectorState => directorStateSchema.parse({
  schemaVersion: 1,
  projectId,
  houseStyle: 'apollo-11-archive-opening',
  status: 'DIRECTING',
  activeCheckpoint: 'TOPIC_PROMISE',
  tokenTarget: 50_000,
  createdAt: now,
  updatedAt: now,
  checkpoints: checkpointIds.map((id, index) => ({
    id,
    title: titles[id],
    status: index === 0 ? 'AWAITING_CHOICE' : 'LOCKED',
    options: index === 0 ? episodeOneTopicOptions : [],
  })),
});

export const saveDirectorState = async (state: DirectorState, filename?: string) => {
  const target = path.resolve(filename ?? path.join('public/projects', state.projectId, 'director-state.json'));
  await mkdir(path.dirname(target), {recursive: true});
  await writeFile(target, `${JSON.stringify(directorStateSchema.parse(state), null, 2)}\n`);
  return target;
};

export const loadDirectorState = async (filename: string) => directorStateSchema.parse(JSON.parse(await readFile(filename, 'utf8')));

export const chooseDirectorOption = async (filename: string, optionId: string, now = new Date().toISOString()) => {
  const state = await loadDirectorState(filename);
  const index = state.checkpoints.findIndex((checkpoint) => checkpoint.id === state.activeCheckpoint);
  const checkpoint = state.checkpoints[index];
  if (checkpoint.status !== 'AWAITING_CHOICE') throw new Error(`${checkpoint.title} is not awaiting a choice`);
  if (!checkpoint.options.some((option) => option.id === optionId)) throw new Error(`Unknown option ${optionId}`);
  const backup = filename.replace(/\.json$/, `.before-${checkpoint.id.toLowerCase()}-${now.replace(/[:.]/g, '-')}.json`);
  await copyFile(filename, backup);
  checkpoint.status = 'SELECTED';
  checkpoint.selectedOptionId = optionId;
  checkpoint.selectedAt = now;
  const next = state.checkpoints[index + 1];
  if (next) {
    state.activeCheckpoint = next.id;
    state.status = 'PRODUCING';
  } else {
    state.status = 'COMPLETE';
  }
  state.updatedAt = now;
  await writeFile(filename, `${JSON.stringify(directorStateSchema.parse(state), null, 2)}\n`);
  return {state, backup};
};

export const setDirectorCheckpointOptions = async (filename: string, checkpointId: (typeof checkpointIds)[number], options: DirectorChoice[], now = new Date().toISOString()) => {
  const state = await loadDirectorState(filename);
  if (state.activeCheckpoint !== checkpointId) throw new Error(`Active checkpoint is ${state.activeCheckpoint}, not ${checkpointId}`);
  if (options.length < 2 || options.length > 4) throw new Error('A directing checkpoint requires 2–4 options');
  const checkpoint = state.checkpoints.find((item) => item.id === checkpointId)!;
  const backup = filename.replace(/\.json$/, `.before-options-${checkpointId.toLowerCase()}-${now.replace(/[:.]/g, '-')}.json`);
  await copyFile(filename, backup);
  checkpoint.options = z.array(choiceSchema).parse(options);
  checkpoint.status = 'AWAITING_CHOICE';
  state.status = 'DIRECTING';
  state.updatedAt = now;
  await writeFile(filename, `${JSON.stringify(directorStateSchema.parse(state), null, 2)}\n`);
  return {state, backup};
};
