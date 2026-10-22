export const samplingRoster: [string, number][] = [
  ['Mesquite Valley', 12], ['Stateline Pass', 25], ['ISEGS North', 53],
  ['ISEGS South', 10], ['Southpah', 39], ['Nipton', 32],
  ['Silver State', 21], ['Sheep', 21], ['McCullough Pass', 47],
  ['Eldorado Valley', 15], ['Piute Valley', 24],
];

export const figureHtml: Record<number, string> = {
  1: `<div class="figure-label">FIGURE 1 · STUDY GEOGRAPHY</div>
    <h3>Eleven named sampling locations</h3>
    <p>The ten approximately 1 km² survey plots and the broader Piute Valley area are represented by <strong>aggregate coordinate means</strong> calculated from the USGS individual records. Marker size distinguishes the sampling designs; it does not show a measured area.</p>
    <div class="evidence-key"><span><i class="legend-dot legend-dot--site"></i> Derived from observations</span><span><i class="legend-dot legend-dot--solar"></i> Public GIS context</span></div>
    <div class="site-roster">${samplingRoster.map(([name, n]) => `<div><span>${name}${name === 'Piute Valley' ? ' <em>area</em>' : ''}</span><strong>${n}</strong></div>`).join('')}</div>
    <p class="fineprint">Named valleys and passes are geographic reference points. The map does not draw plot boundaries, a formal study boundary, or individual tortoise positions. The solar overlay covers only one authorized BLM right-of-way.</p>`,
  2: `<div class="figure-label">FIGURE 2 · LANDSCAPE RESISTANCE</div>
    <h3>Four tested cost concepts</h3>
    <p>Select a concept to inspect the relevant <strong>geographic feature</strong>. The paper's resistance rasters were not recovered, so no spatial cost surface is displayed.</p>
    <div class="concept-list">
      <button data-concept="uniform" type="button"><strong>Uniform landscape</strong><small>Constant cost of 0.001 in the paper's baseline model.</small></button>
      <button data-concept="highway" type="button"><strong>Highway resistance</strong><small>I-15 corridor hypothesis; Census centerline shown.</small></button>
      <button data-concept="railway" type="button"><strong>Railway resistance</strong><small>Rail corridor hypothesis; Census rail lines shown.</small></button>
      <button data-concept="habitat" type="button"><strong>Habitat-based resistance</strong><small>Cost = 1 − modeled habitat suitability.</small></button>
    </div>
    <p class="fineprint">Selection changes only contextual line overlays. These are modeled costs, not observed tortoise movements. Habitat suitability came from Nussear et al. (2009); its original raster and the paper's transformations are unavailable here.</p>`,
  3: `<div class="figure-label">FIGURE 3 · GENETIC STRUCTURE</div>
    <h3>Three broad groupings</h3>
    <p>Using 20 microsatellite markers, the authors summarized broad regional structure at K = 3.</p>
    <div class="group-list"><div><b>01</b><span>Ivanpah / Mesquite</span></div><div><b>02</b><span>McCullough Pass</span></div><div><b>03</b><span>Eldorado / Piute</span></div></div>
    <p class="fineprint">These names summarize reported genetic clusters, not sharp geographic boundaries. The USGS release has genotypes and coordinates, but no site-level STRUCTURE assignment proportions. Pie charts would imply unavailable values, so none are drawn.</p>`,
  4: `<div class="figure-label">FIGURE 4 · SPATIAL GENETIC PATTERNS</div>
    <h3>Two spatial axes</h3>
    <div class="axis-card"><span>AXIS 1</span><strong>Broad regional contrast</strong><p>The paper describes a division between Ivanpah / Mesquite and locations farther east.</p></div>
    <div class="axis-card"><span>AXIS 2</span><strong>Finer Ivanpah pattern</strong><p>A second axis describes additional east–west structure within the Ivanpah region.</p></div>
    <p class="fineprint">No published site scores were recovered. The black and white score signs in the paper's figure do not mean “connected” and “blocked.” These cards report pattern only, without invented scores or directions of movement.</p>`,
  5: `<div class="figure-label">RESEARCH FINDINGS · REPORTED VALUES</div>
    <h3>Evidence and model comparison</h3>
    <div class="metric-row"><div><strong>299</strong><span>individuals</span></div><div><strong>20</strong><span>microsatellite markers</span></div><div><strong>11</strong><span>sampling locations</span></div></div>
    <div class="model-result"><span>Railway + I-15 + Habitat</span><strong>0.53</strong><div class="weight-track"><i style="width:53%"></i></div><small>AIC weight · reported R² 0.90</small></div>
    <div class="model-result"><span>Railway + Habitat</span><strong>0.47</strong><div class="weight-track"><i style="width:47%"></i></div><small>AIC weight · reported R² 0.90</small></div>
    <p class="result-note">Reported ΔAIC = 0.21. That is very little separation between the two models.</p>
    <p class="fineprint">The printed parameter counts, log-likelihoods, and AIC values are internally inconsistent under the standard AIC formula. Ranking and weights are presented as the authors reported them, not independently verified. The parallel railway and highway are difficult to separate statistically, and there is no preconstruction genetic baseline.</p>`,
};
