import rawManifest from '../../public/projects/greenwood-1921/manifest.json';
import {parseManifest} from './schema';

export const sampleManifest = parseManifest(rawManifest);
