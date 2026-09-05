export type Shot = {
  id: string;
  start: number;
  duration: number;
  src: string;
  credit: string;
  objectPosition: string;
  scaleFrom: number;
  scaleTo: number;
  translateX?: number;
  translateY?: number;
  editorialPurpose: string;
  assetRationale: string;
};

export const apolloOpeningShots: Shot[] = [
  {id: 'launch', start: 0, duration: 75, src: 'projects/apollo-11-opening/archive/saturn-v-launch.jpg', credit: 'NASA/MSFC · 6901001', objectPosition: '50% 45%', scaleFrom: 1.08, scaleTo: 1.18, translateY: 18, editorialPurpose: 'Establish the scale and physical departure of Apollo 11.', assetRationale: 'A NASA launch photograph immediately grounds the opening in the real mission.'},
  {id: 'prelaunch', start: 75, duration: 105, src: 'projects/apollo-11-opening/archive/prelaunch.jpg', credit: 'NASA/JSC · JSC2007E034221', objectPosition: '50% 62%', scaleFrom: 1.02, scaleTo: 1.12, translateX: -15, editorialPurpose: 'Move from spectacle to the spacecraft that must travel beyond contact.', assetRationale: 'The close pre-launch view makes the mission hardware tangible before the story shifts to space.'},
  {id: 'transmission', start: 180, duration: 120, src: 'projects/apollo-11-opening/archive/tv-transmission.jpg', credit: 'NASA/JSC · S69-39532', objectPosition: '50% 50%', scaleFrom: 1.05, scaleTo: 1.17, translateX: 12, editorialPurpose: 'Introduce the fragile communications link between Apollo and Earth.', assetRationale: 'The authentic transmission photograph visually supports the narration about radio contact.'},
  {id: 'hardware', start: 300, duration: 60, src: 'projects/apollo-11-opening/archive/lunar-module-assembly.jpg', credit: 'NASA/KSC · 624073MAIN', objectPosition: '50% 48%', scaleFrom: 1.03, scaleTo: 1.1, translateY: -8, editorialPurpose: 'Bridge the silence of communications to the machinery operating without outside help.', assetRationale: 'A technical NASA image emphasizes the real vehicle and its mechanical stakes.'},
  {id: 'control-wide', start: 360, duration: 150, src: 'projects/apollo-11-opening/archive/mission-control.jpg', credit: 'NASA/JSC · S69-39817', objectPosition: '50% 48%', scaleFrom: 1.02, scaleTo: 1.1, translateX: -10, editorialPurpose: 'Show the people on Earth who temporarily lost all contact and control.', assetRationale: 'The wide Mission Control view directly depicts the team named in the narration.'},
  {id: 'orbit-wide', start: 510, duration: 120, src: 'projects/apollo-11-opening/archive/lunar-module-orbit.jpg', credit: 'NASA/KSC · AS11-44-6642', objectPosition: '50% 50%', scaleFrom: 1, scaleTo: 1.08, translateY: 8, editorialPurpose: 'Reveal Apollo 11 in lunar orbit as the engine burn succeeds.', assetRationale: 'The real orbital photograph communicates location and outcome more clearly than a diagram.'},
  {id: 'control-detail', start: 630, duration: 120, src: 'projects/apollo-11-opening/archive/mission-control.jpg', credit: 'NASA/JSC · S69-39817 · DETAIL CROP', objectPosition: '50% 82%', scaleFrom: 1.25, scaleTo: 1.38, translateX: 18, editorialPurpose: 'Return tightly to the consoles as the signal comes back.', assetRationale: 'A distinct detail crop turns the reused source into a purposeful reaction beat focused on operators.'},
  {id: 'orbit-detail', start: 750, duration: 150, src: 'projects/apollo-11-opening/archive/lunar-module-orbit.jpg', credit: 'NASA/KSC · AS11-44-6642 · DETAIL CROP', objectPosition: '34% 72%', scaleFrom: 1.32, scaleTo: 1.48, translateX: -18, editorialPurpose: 'End on the spacecraft and the Moon, holding the approaching landing as the final idea.', assetRationale: 'A distinct close crop isolates the lunar module and supplies a restrained visual conclusion.'},
];

export const apolloOpeningCaptions = [
  {start: 30, end: 165, text: 'Before Apollo 11 could land on the Moon, it had to disappear from Earth.'},
  {start: 165, end: 360, text: 'On July 19, 1969, the spacecraft slipped behind the Moon, and every radio link went silent.'},
  {start: 360, end: 510, text: 'Mission Control could no longer see the crew, hear them, or help them.'},
  {start: 510, end: 651, text: 'In that blackout, Apollo 11 fired its engine and entered lunar orbit.'},
  {start: 651, end: 804, text: 'When the signal returned, the spacecraft was exactly where it needed to be.'},
  {start: 804, end: 890, text: 'The landing was one day away.'},
];
