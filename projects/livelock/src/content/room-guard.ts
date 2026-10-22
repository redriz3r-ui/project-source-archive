// Conceal document at document_start; reveal only after background authorization.
let style:HTMLStyleElement|null=null;
let lease=0;
let enabled=true;
function hide(){if(style?.isConnected)return;style=document.createElement('style');style.textContent='html{visibility:hidden!important}';(document.documentElement||document).appendChild(style);}
function show(){style?.remove();style=null;}
hide();
let sequence=0;
async function check(){
  const seq=++sequence;hide();
  try{
    const response=await chrome.runtime.sendMessage({type:'guard'});
    if(seq!==sequence)return;
    if(response?.ok&&response.value.allowed){enabled=response.value.enabled;lease=response.value.expiresAtMs;show();}
    else location.replace(chrome.runtime.getURL('blocked.html'));
  }catch{hide();}
}
void check();
let lastUrl=location.href;
setInterval(()=>{if(location.href!==lastUrl){lastUrl=location.href;void check();}else if(enabled&&Date.now()>=lease){hide();void check();}},250);
addEventListener('popstate',()=>void check());
addEventListener('hashchange',()=>void check());
addEventListener('focus',()=>void check());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)void check();});
chrome.runtime.onMessage.addListener(message=>{if(message?.type==='recheck')void check();});
