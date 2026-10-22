export type Place = {
  id: string;
  name: string;
  subtitle: string;
  coordinates: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
  source: string;
  note: string;
};

// Navigation targets are documented geographic reference points, never tortoise sample locations.
export const places: Place[] = [
  { id: 'ivanpah', name: 'Ivanpah Valley', subtitle: 'Study center', coordinates: [-115.3341567, 35.499985], zoom: 10.6, bearing: -18, pitch: 64, source: 'https://geo.mytopo.com/feature/nevada/clark/basin/841317/ivanpah-valley/', note: 'GNIS basin reference point; not a survey plot.' },
  { id: 'mesquite', name: 'Mesquite Valley', subtitle: 'Mesquite Lake viewpoint', coordinates: [-115.58528, 35.71998], zoom: 10.7, bearing: 31, pitch: 64, source: 'https://www.mindat.org/loc-294717.html', note: 'Verified Mesquite Lake point within the valley; not a survey plot.' },
  { id: 'stateline', name: 'Stateline Pass', subtitle: 'Western mountain passage', coordinates: [-115.43694, 35.65554], zoom: 11.7, bearing: 18, pitch: 68, source: 'https://mapcarta.com/23371676', note: 'Named gap reference point; not the study plot coordinate.' },
  { id: 'mccullough', name: 'McCullough Pass', subtitle: 'Eastern mountain passage', coordinates: [-115.1688771, 35.7366487], zoom: 11.7, bearing: -28, pitch: 68, source: 'https://geo.mytopo.com/feature/nevada/clark/gap/842004/mccullough-pass/', note: 'GNIS gap reference point; not the study plot coordinate.' },
  { id: 'eldorado', name: 'Eldorado Valley', subtitle: 'Eastern valley', coordinates: [-114.97999, 35.79165], zoom: 10.8, bearing: -24, pitch: 62, source: 'https://mapcarta.com/23352956', note: 'Valley reference point; not a survey plot.' },
  { id: 'piute', name: 'Piute Valley', subtitle: 'Searchlight edge viewpoint', coordinates: [-114.9197005, 35.4652685], zoom: 10.4, bearing: 22, pitch: 62, source: 'https://www.topozone.com/nevada/clark-nv/city/searchlight/', note: 'Verified Searchlight point at the northern edge of Piute Valley; not the broader Piute sampling area.' }
];

export const studyBounds: [[number, number], [number, number]] = [[-115.67, 35.32], [-114.82, 35.86]];
