import domains from '../rules/adult-domains.json';
import directoryDomains from '../rules/directory-domains.json';
import directoryMetadata from '../rules/directory-metadata.json';
import paths from '../rules/blocked-paths.json';
import metadata from '../rules/blocklist-metadata.json';
const domainSet = new Set([...domains,...directoryDomains]);
const patterns = paths.map(path=>new RegExp(path.regex,'i'));
export const blocklistInfo = {domainCount:domainSet.size,directoryDomainCount:directoryMetadata.domainCount,directoryListings:directoryMetadata.listingCount,directoryUpdatedAt:directoryMetadata.retrievedAt,retrievedAt:metadata.retrievedAt,pathLabels:paths.map(path=>path.label)};
/** Suffix lookup avoids scanning the entire category list on every tab/UI event. */
export function builtinBlockedUrl(url: string): boolean {
  try {
    const parsed=new URL(url);
    if(!['http:','https:'].includes(parsed.protocol))return false;
    const labels=parsed.hostname.toLowerCase().split('.');
    for(let i=0;i<labels.length-1;i++)if(domainSet.has(labels.slice(i).join('.')))return true;
    return patterns.some(pattern=>pattern.test(parsed.href));
  } catch {return false;}
}
