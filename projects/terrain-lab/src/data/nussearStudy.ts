import { validateStudyMetadata, type StudyMetadata } from './studyMetadata.ts';

export const nussearStudy = {
  schemaVersion: 'terrain-lab-study/v1',
  id: 'nussear-2009-desert-tortoise-habitat',
  title: 'Modeling habitat of the desert tortoise (Gopherus agassizii) in the Mojave and parts of the Sonoran Deserts of California, Nevada, Utah, and Arizona',
  authors: [
    'Kenneth E. Nussear', 'Todd C. Esque', 'Richard D. Inman', 'Leila Gass',
    'Kathryn A. Thomas', 'Cynthia S.A. Wallace', 'Joan B. Blainey',
    'David M. Miller', 'Robert H. Webb',
  ],
  publicationYear: 2009,
  doi: '10.3133/ofr20091102',
  sourceUrl: 'https://pubs.usgs.gov/publication/ofr20091102',
  discipline: 'conservation ecology and habitat modeling',
  studyArea: {
    name: 'Mojave Desert and parts of the Sonoran Desert in California, Nevada, Utah, and Arizona',
    sourceUrl: 'https://pubs.usgs.gov/publication/ofr20091102',
    // The named model region is not a verified polygon or a set of observation sites.
  },
  datasets: [
    {
      id: 'presence-records',
      title: 'Field-collected desert tortoise presence records used for model fitting',
      role: 'observed-geography',
      availability: 'not-recovered',
      sourceUrl: 'https://pubs.usgs.gov/publication/ofr20091102',
      provenance: 'The USGS report describes field-collected presence data as Maxent inputs; its publication page does not identify a separate downloadable point-record package.',
      limitations: ['No observation coordinates are registered or inferred from the mapped study region.', 'A figure showing presence sites is not a downloadable point dataset.'],
    },
    {
      id: 'environmental-layers',
      title: 'Environmental layers companion package',
      role: 'derived-output',
      availability: 'external',
      sourceUrl: 'https://pubs.usgs.gov/publication/ofr20091102',
      format: 'ZIP of gridded environmental layers',
      provenance: 'USGS Open-File Report 2009-1102 lists a 27.4 MB Environmental Layers companion ZIP; the report describes 16 gridded environmental variables used in modeling.',
      limitations: ['These are model inputs assembled from multiple environmental sources, not tortoise observations.', 'Source dates and any component-specific rights require inspection before reuse of individual layers.'],
    },
    {
      id: 'habitat-model',
      title: 'Binned predicted desert tortoise habitat potential',
      role: 'model-prediction',
      availability: 'local',
      localPath: '/data/nussear-2009/habitat-potential-3857.tif',
      sourceUrl: 'https://pubs.usgs.gov/of/2009/1102/ofr20091102_dt_Habitat_Model.zip',
      format: 'GeoTIFF derived from published ESRI ASCII grid',
      derivedFrom: ['presence-records', 'environmental-layers'],
      provenance: 'Original USGS Habitat Model ZIP is preserved at /data/nussear-2009/ofr20091102_dt_Habitat_Model.zip (SHA-256 c33d3088e9a5b1c2c653e215b3780657bba5a81d72d98638e126871068dc9ee0). Its 566 × 729 ESRI ASCII grid uses NAD83 / UTM zone 11N (EPSG:26911). Reprojected to EPSG:3857 GeoTIFF with GDAL nearest-neighbor resampling and explicit NoData -9999 for the existing Terrain Lab raster viewer.',
      limitations: ['Published values are binned from 0 to 1 in 0.1 increments; they are model predictions, not measurements, current occupancy, or a study boundary.', 'The reprojection changes the display grid and cell counts, though nearest-neighbor resampling retains source class values.', 'The model does not account for later anthropogenic habitat change.'],
    },
  ],
  uncertainties: [
    'No machine-readable study-area polygon or observation coordinates were verified for this catalog entry.',
    'The habitat-model companion ZIP has been inspected and loaded; the separate Environmental Layers ZIP has not been ingested.',
    'A single verified temporal coverage for all model inputs has not been established.',
  ],
} satisfies StudyMetadata;

validateStudyMetadata(nussearStudy);
