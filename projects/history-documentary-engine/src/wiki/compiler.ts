import {createHash} from 'node:crypto';
import {wikiArticleSchema,type WikiArticle} from './schema';

type ParseResponse={parse?:{title?:string;pageid?:number;revid?:number;text?:string|{'*'?:string};images?:string[];links?:Array<{title?:string;exists?:string|boolean}>}};
const ignored=/^(References|Notes|Citations|Sources|Bibliography|External links|Further reading|See also)$/i;
const entities:Record<string,string>={amp:'&',quot:'"',apos:"'",nbsp:' ',ndash:'–',mdash:'—',rsquo:'’',lsquo:'‘',ldquo:'“',rdquo:'”'};
export const plainText=(html:string)=>html
  .replace(/<sup\b[^>]*>[\s\S]*?<\/sup>/gi,' ').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,' ').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,' ')
  .replace(/<[^>]+>/g,' ').replace(/&(#x?[0-9a-f]+|[a-z]+);/gi,(_m,key:string)=>{if(key[0]==='#'){const hex=key[1]?.toLowerCase()==='x';return String.fromCodePoint(parseInt(key.slice(hex?2:1),hex?16:10));}return entities[key.toLowerCase()]??`&${key};`;})
  .replace(/\[\s*(?:citation needed|clarification needed|who\?|when\?|where\?)\s*\]/gi,'').replace(/\s+/g,' ').trim();
export const sentenceSplit=(text:string)=>text.split(/(?<=[.!?])\s+(?=[A-Z0-9“"'])/).map(x=>x.trim()).filter(Boolean);
const slug=(value:string)=>value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');

export const compileParsedWikipedia=(data:ParseResponse,retrievedAt=new Date().toISOString()):WikiArticle=>{
  const parsed=data.parse;const html=typeof parsed?.text==='string'?parsed.text:parsed?.text?.['*'];if(!parsed?.title||!parsed.pageid||!parsed.revid||!html)throw new Error('Wikipedia response is missing page metadata or article HTML');
  const tokens=[...html.matchAll(/<(h[2-6]|p)\b[^>]*?(?:id="([^"]+)")?[^>]*>([\s\S]*?)<\/\1>/gi)];
  const lead:WikiArticle['lead']=[];const sections:WikiArticle['sections']=[];const stack:Array<{level:number;id:string}>=[];let current:WikiArticle['sections'][number]|null=null;let paragraphIndex=0;
  for(const token of tokens){const tag=token[1].toLowerCase();const text=plainText(token[3]);if(!text)continue;
    if(tag==='p'){if(text.length<25)continue;const sentences=sentenceSplit(text);if(!sentences.length)continue;const linkedTitles=[...token[3].matchAll(/href="(?:\.\/|\/wiki\/)([^"#?]+)(?:[#?][^"]*)?"/gi)].map(match=>{try{return decodeURIComponent(match[1].replace(/_/g,' '));}catch{return match[1].replace(/_/g,' ');}}).filter(title=>!title.includes(':'));const paragraph={id:`p-${String(++paragraphIndex).padStart(4,'0')}`,text,sentences,wordCount:text.split(/\s+/).length,linkedTitles:[...new Set(linkedTitles)]};if(current)current.paragraphs.push(paragraph);else lead.push(paragraph);continue;}
    const level=Number(tag.slice(1));const title=text.replace(/\[edit\]$/i,'').trim();current=null;if(ignored.test(title))break;
    while(stack.length&&stack.at(-1)!.level>=level)stack.pop();const id=`s-${String(sections.length+1).padStart(3,'0')}-${slug(title)}`;
    current={id,index:sections.length,level,title,anchor:token[2]??slug(title),parentId:stack.at(-1)?.id??null,paragraphs:[],wordCount:0};sections.push(current);stack.push({level,id});
  }
  for(const section of sections)section.wordCount=section.paragraphs.reduce((n,p)=>n+p.wordCount,0);
  const words=lead.reduce((n,p)=>n+p.wordCount,0)+sections.reduce((n,s)=>n+s.wordCount,0);
  const base={schemaVersion:1 as const,source:'Wikipedia' as const,language:'en' as const,title:parsed.title,pageId:parsed.pageid,revisionId:parsed.revid,canonicalUrl:`https://en.wikipedia.org/wiki/${encodeURIComponent(parsed.title.replace(/ /g,'_'))}`,license:'CC BY-SA 4.0' as const,retrievedAt,lead,sections,
    images:[...new Set(parsed.images??[])].filter(name=>/\.(?:jpe?g|png|webp|svg)$/i.test(name)).map(filename=>({filename})),links:(parsed.links??[]).filter(link=>link.title).map(link=>({title:link.title!,exists:link.exists!==undefined})),
    totals:{words,paragraphs:lead.length+sections.reduce((n,s)=>n+s.paragraphs.length,0),sections:sections.length,estimatedReadingMinutes:Number((words/220).toFixed(1))}};
  const contentHash=createHash('sha256').update(JSON.stringify(base)).digest('hex');return wikiArticleSchema.parse({...base,contentHash});
};
