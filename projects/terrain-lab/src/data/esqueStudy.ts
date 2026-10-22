import { validateStudyMetadata, type StudyMetadata } from './studyMetadata.ts';

export const esqueStudy = {
  schemaVersion: 'terrain-lab-study/v1',
  id: 'esque-2023-joshua-tree-distribution',
  title: 'Unprecedented distribution data for Joshua trees (Yucca brevifolia and Y. jaegeriana) reveal contemporary climate associations of a Mojave Desert icon',
  authors: ['Todd C. Esque', 'Daniel F. Shryock', 'Gabrielle A. Berry', 'Felicia C. Chen', 'Lesley A. DeFalco', 'Sabrina M. Lewicki', 'Brent L. Cunningham', 'Eddie J. Gaylord', 'Caitlan S. Poage', 'Gretchen E. Gantz', 'Ross A. Van Gaalen', 'Ben O. Gottsacker', 'Amanda M. McDonald', 'Jeremy B. Yoder', 'Christopher I. Smith', 'Kenneth E. Nussear'],
  publicationYear: 2023,
  doi: '10.3389/fevo.2023.1266892',
  sourceUrl: 'https://www.frontiersin.org/journals/ecology-and-evolution/articles/10.3389/fevo.2023.1266892/full',
  discipline: 'plant biogeography and species distribution modeling',
  studyArea: {
    name: 'Joshua tree ranges in the Mojave Desert and adjacent desert regions of Arizona, California, Nevada, and Utah; no exact study-footprint polygon verified',
    sourceUrl: 'https://www.usgs.gov/data/distribution-data-and-habitat-models-joshua-trees-yucca-brevifolia-and-y-jaegeriana-throughout',
  },
  provenanceUrl: 'https://www.sciencebase.gov/catalog/item/67a2cb3ed34e91a4ffc72e98',
  permissions: 'The Frontiers article is CC BY 4.0. The associated 2025 USGS data release is marked CC0 1.0 Universal.',
  datasets: [
    {
      id: 'hybrid-presence-grid-cells',
      title: 'USGS Joshua tree hybrid-presence grid cells in Nevada',
      role: 'observed-geography',
      availability: 'local',
      localPath: '/data/esque-2023-joshua-tree/hybrid-presence-cells.geojson',
      sourceUrl: 'https://www.sciencebase.gov/catalog/item/67a2cb3ed34e91a4ffc72e98',
      format: 'GeoJSON',
      provenance: 'USGS data release DOI 10.5066/P9NZMDLL (2025), Hybrid_Presence_Cells shapefile. Original components are preserved in research/intake/sources/esque-2023-joshua-tree and checked against publisher MD5 values. Source NAD83 Albers coordinates were converted to WGS84 GeoJSON without simplification. Prepared SHA-256 96e23e42f471fb3d7f6cb90de798ebb426b9a16c8246a6c93e5e330feb715166.',
      permissions: 'The USGS release is marked CC0 1.0 Universal. Cite USGS and the release DOI for provenance.',
      limitations: [
        'Cells show mapped presence, not individual tree coordinates, population counts, or the full occupied range.',
        'The Nevada hybrid-presence subset is not the paper study boundary and is not a model prediction.',
        'No per-cell observation dates or field-versus-imagery validation flags were verified in the source attributes.',
        'The 2025 release supports the 2023 paper, but exact correspondence to the article’s model inputs is unverified.',
      ],
    },
    {
      id: 'hybrid-cell-680349-area',
      title: 'Computed geodesic area of mapped hybrid-presence grid cell 680349',
      role: 'derived-output',
      availability: 'local',
      localPath: '/data/esque-2023-joshua-tree/cell-680349-area.geojson',
      sourceUrl: 'https://www.sciencebase.gov/catalog/item/67a2cb3ed34e91a4ffc72e98',
      format: 'GeoJSON',
      derivedFrom: ['hybrid-presence-grid-cells'],
      provenance: 'Terrain Lab polygon-area/v1 computes Turf geodesic area of source cell 680349 after checking the original source bundle and WGS84 GeoJSON checksums. The output retains the unchanged source cell and a separate computed feature.',
      permissions: 'Derived from the USGS release marked CC0 1.0 Universal; cite USGS and release DOI.',
      limitations: [
        'Area is the geometric area of one mapped grid cell; it is not the area occupied by tree crowns or a species range estimate.',
        'A geometry calculation does not test the paper’s climate associations or model predictions.',
      ],
    },
  ],
  uncertainties: [
    'The USGS release was published in 2025, after the article in 2023; the original article input version has not been established.',
    'No machine-readable footprint for the full study was verified.',
    'The Frontiers article spells C. S. Poage’s given name Caitlan, while the later USGS release uses Caitlin; this record follows the publisher article.',
    'Mapped presence cells are observations at grid resolution, not independent ground verification of every individual cell.',
  ],
} satisfies StudyMetadata;

validateStudyMetadata(esqueStudy);
