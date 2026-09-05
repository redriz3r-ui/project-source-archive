import {contentHash} from '../intelligence/engine';
import type {ClaimRecord,EvidencePassage,SourceRecord} from '../intelligence/schema';

const source=(id:string,title:string,url:string,publisher:string,type:'PRIMARY'|'AUTHORITATIVE_SECONDARY'|'SECONDARY',score:number):SourceRecord=>({schemaVersion:1,id,title,url,publisher,sourceType:type,contentHash:contentHash({title,url}),reliabilityScore:score});
export const manilaSources:SourceRecord[]=[
  source('src-ncca','Philippine History Source Book: World War II in the Philippines','https://ncca.gov.ph/wp-content/uploads/2021/09/PHILIPPINE-HISTORY-SOURCE-BOOK-FINAL-SEP022021.pdf','National Commission for Culture and the Arts','AUTHORITATIVE_SECONDARY',94),
  source('src-army-luzon','Luzon Campaign','https://history.army.mil/Portals/143/Images/Publications/Publication%20By%20Title%20Images/C%20Img/campaigns-wwii/pdf/21.pdf','U.S. Army Center of Military History','AUTHORITATIVE_SECONDARY',96),
  source('src-army-triumph','Triumph in the Philippines','https://history.army.mil/portals/143/Images/Publications/catalog/5-10.pdf','U.S. Army Center of Military History','AUTHORITATIVE_SECONDARY',96),
  source('src-memorare','Memorare — Manila 1945 Historical Marker','https://philhistoricsites.nhcp.gov.ph/registry_database/memorare-manila-1945/','National Historical Commission of the Philippines','AUTHORITATIVE_SECONDARY',98),
  source('src-intramuros','Battle of Manila: Humanity Amidst the Carnage','https://intramuros.gov.ph/2021/02/27/battle-of-manila-humanity-amidst-the-carnage/','Intramuros Administration, Republic of the Philippines','AUTHORITATIVE_SECONDARY',94),
  source('src-national-museum','History of the National Museum','https://www.nationalmuseum.gov.ph/about-us/history/','National Museum of the Philippines','AUTHORITATIVE_SECONDARY',95),
  source('src-finance-building','National Museum of Anthropology History','https://www.nationalmuseum.gov.ph/our-museums/national-museum-of-anthropology/nma-history/','National Museum of the Philippines','AUTHORITATIVE_SECONDARY',95),
  source('src-pia','Remembering the 1945 Battle of Manila','https://pia.gov.ph/news/luzon/ncr/painful-past-remembering-the-horrific-1945-battle-of-manila/','Philippine Information Agency','AUTHORITATIVE_SECONDARY',90),
  source('src-yamashita-trial','United States v. Tomoyuki Yamashita trial record','https://tile.loc.gov/storage-services/service/ll/llmlp/Yamashita-trial_Vol_21-34_PT-23Nov1945/Yamashita-trial_Vol_21-34_PT-23Nov1945.pdf','Library of Congress','PRIMARY',92),
];
const evidence=(id:string,sourceId:string,text:string,questions:string[]):EvidencePassage=>({schemaVersion:1,id,sourceId,text,locator:`source-summary:${id}`,questionIds:questions,invalidated:false});
export const manilaPassages:EvidencePassage[]=[
  evidence('ev-1941-bombing','src-ncca','Japanese forces bombed Manila and surrounding areas after the attack on Pearl Harbor in December 1941.',['q-1941']),
  evidence('ev-open-city','src-ncca','MacArthur declared Manila an open city in an attempt to prevent its destruction, but bombing continued.',['q-1941']),
  evidence('ev-yamashita-order','src-army-luzon','General Yamashita regarded Manila as indefensible and ordered vital installations and bridges destroyed before evacuation.',['q-command']),
  evidence('ev-iwabuchi','src-army-luzon','Rear Admiral Sanji Iwabuchi chose to resist inside Manila instead of evacuating, organizing a naval defense force with additional army battalions.',['q-command']),
  evidence('ev-garrison-range','src-army-luzon','Official Army accounts describe a Japanese Manila defense force in the approximate range of sixteen to seventeen thousand personnel.',['q-command']),
  evidence('ev-restrictions','src-army-luzon','MacArthur initially imposed stringent restrictions on American artillery and air support in an effort to protect the city and civilians.',['q-destruction']),
  evidence('ev-street-fighting','src-army-luzon','The battle became a month of street-to-street and building-to-building combat as resistance hardened south of the Pasig River.',['q-destruction']),
  evidence('ev-intramuros-fire','src-army-triumph','American artillery, tanks, tank destroyers and mortars conducted heavy preparatory fire against fortified Intramuros before the February 23 assault.',['q-destruction']),
  evidence('ev-causes','src-memorare','The Manila memorial attributes civilian deaths mainly to atrocities by Japanese forces and casualties from heavy American artillery barrages.',['q-civilians','q-destruction']),
  evidence('ev-burning','src-intramuros','Philippine historical authorities describe hundreds of city blocks razed by Japanese fire or subsequently destroyed by American artillery.',['q-destruction']),
  evidence('ev-civilian-estimate','src-memorare','The official historical marker commemorates more than one hundred thousand defenseless civilians killed during the February 3 to March 3 battle.',['q-civilians']),
  evidence('ev-casualty-uncertainty','src-pia','Government commemorations characterize one hundred thousand Filipino civilian deaths as an estimate rather than a precise count.',['q-civilians']),
  evidence('ev-national-collections','src-national-museum','The Legislative Building and Bureau of Science were reduced to ruins, destroying virtually the entire national collections stored there.',['q-legacy']),
  evidence('ev-finance-building','src-finance-building','The Department of Finance Building endured seven days of heavy American artillery fire while serving as part of the Japanese defensive position.',['q-legacy','q-destruction']),
  evidence('ev-end-date','src-army-triumph','Organized resistance in Manila ended by March 3, 1945, after nearly a month of fighting.',['q-command']),
  evidence('ev-trial-record','src-yamashita-trial','The postwar Yamashita proceedings preserved testimony and exhibits concerning atrocities committed in Manila.',['q-civilians']),
];
const claim=(id:string,statement:string,passages:string[],confidence:'HIGH'|'MEDIUM'='HIGH'):ClaimRecord=>({schemaVersion:1,id,statement,evidencePassageIds:passages,confidence,status:'APPROVED'});
export const manilaClaims:ClaimRecord[]=[
  claim('cl-1941-bombing','Japanese forces bombed Manila and its surroundings in December 1941.',['ev-1941-bombing']),
  claim('cl-open-city','Manila was declared an open city in an unsuccessful effort to spare it from destruction.',['ev-open-city']),
  claim('cl-evacuation-order','Yamashita ordered an evacuation of Manila after destroying militarily useful infrastructure.',['ev-yamashita-order']),
  claim('cl-iwabuchi-resisted','Iwabuchi instead organized a last-stand defense inside the capital.',['ev-iwabuchi']),
  claim('cl-garrison-range','The Japanese defense force numbered approximately sixteen to seventeen thousand.',['ev-garrison-range'],'MEDIUM'),
  claim('cl-support-restricted','American air and artillery support was initially restricted to reduce harm to Manila.',['ev-restrictions']),
  claim('cl-urban-battle','The fight developed into nearly a month of close urban combat.',['ev-street-fighting','ev-end-date']),
  claim('cl-heavy-artillery','American forces later used heavy artillery and direct fire against fortified positions, including Intramuros.',['ev-intramuros-fire','ev-finance-building']),
  claim('cl-dual-causes','Civilians died both in Japanese atrocities and under American artillery fire.',['ev-causes']),
  claim('cl-blocks-destroyed','More than six hundred city blocks were razed by Japanese fire or finished off by American artillery.',['ev-burning'],'MEDIUM'),
  claim('cl-civilian-estimate','Approximately one hundred thousand Filipino civilians died; the number is an estimate, not an exact count.',['ev-civilian-estimate','ev-casualty-uncertainty'],'MEDIUM'),
  claim('cl-collections-lost','The destruction erased major civic buildings and virtually the entire wartime national collection.',['ev-national-collections']),
  claim('cl-battle-ended','The Battle of Manila lasted from February 3 through March 3, 1945.',['ev-civilian-estimate','ev-end-date']),
  claim('cl-trial-evidence','Postwar proceedings preserved testimony and exhibits about atrocities in Manila.',['ev-trial-record'],'MEDIUM'),
];
export const manilaConflicts=[
  {schemaVersion:1,id:'conf-garrison-count',claimIds:['cl-garrison-range'],type:'RANGE_RECONCILIATION',resolution:'Use 16,000–17,000 or “roughly sixteen thousand”; never present a single exact number.',status:'RESOLVED'},
  {schemaVersion:1,id:'conf-civilian-count',claimIds:['cl-civilian-estimate'],type:'ESTIMATE_PRECISION',resolution:'Use “approximately 100,000” and explicitly identify it as an estimate.',status:'RESOLVED'},
];

