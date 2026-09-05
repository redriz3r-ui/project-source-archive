import type {StickFigureProof} from './schema';

export const magsaysayStickProof: StickFigureProof = {
  location: 'MALACAÑANG',
  year: '1953',
  archiveSrc: 'wiki-tests/ramon-magsaysay/media/magsaysay-inauguration.jpg',
  portraitSrc: 'wiki-tests/ramon-magsaysay/media/magsaysay-official.jpg',
  publicSrc: 'wiki-tests/ramon-magsaysay/media/malacanang-public.jpg',
  archiveCredit: 'Wikimedia Commons · Public domain',
  audioSrc: 'wiki-tests/ramon-magsaysay/audio/rm-05.wav',
  characters: [
    {id: 'magsaysay', role: 'PRESIDENT', x: 765, y: 470, scale: 1.16, facing: -1, shirt: '#f7eed7', accent: '#d6aa45'},
    {id: 'citizen-1', role: 'CITIZEN', x: 240, y: 535, scale: 0.9, facing: 1, shirt: '#d9604c'},
    {id: 'citizen-2', role: 'CITIZEN', x: 155, y: 545, scale: 0.82, facing: 1, shirt: '#4d83a8'},
    {id: 'citizen-3', role: 'CITIZEN', x: 70, y: 552, scale: 0.76, facing: 1, shirt: '#d5a63e'},
  ],
};
