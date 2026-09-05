export type StickCharacter = {
  id: string;
  role: 'PRESIDENT' | 'CITIZEN';
  x: number;
  y: number;
  scale?: number;
  facing?: 1 | -1;
  shirt?: string;
  accent?: string;
};

export type StickFigureProof = {
  location: string;
  year: string;
  archiveSrc: string;
  portraitSrc: string;
  publicSrc: string;
  archiveCredit: string;
  audioSrc: string;
  characters: StickCharacter[];
};
