const el = document.getElementById('screen');
const titles = {top_left:'Focus', top_right:'Actions', bottom_left:'Timeline', bottom_right:'Context'};
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function val(v){if(v==null)return 'None'; if(Array.isArray(v))return v.map(x=>typeof x==='object'?JSON.stringify(x):x).join(' · '); if(typeof v==='object')return JSON.stringify(v); return String(v);}
async function baseSvg(image,data){
  try{
    let t = await (await fetch(`/images/${image}.svg`)).text();
    const d=data||{};
    const r={title:d.title||d.name||'Agent CRM',deal_name:d.name||d.deal_name||'Deal',contact_name:d.name||d.contact_name||'Contact',actions:val(d.actions),fields:val(d.fields),items:val(d.items),links:val(d.links),pipeline:val(d.pipeline||d.related||d.overdue_tasks),series:val(d.series)};
    for(const [k,v] of Object.entries(r)) t=t.split(`{${k}}`).join(esc(v));
    return `<div class="base-svg">${t}</div>`;
  }catch{return '';}
}
function details(data){return `<div class="kv">${Object.entries(data||{}).map(([k,v])=>`<b>${esc(k)}</b><span>${esc(val(v))}</span>`).join('')}</div>`;}
async function refresh(){
  let layout=window.SCREEN_LAYOUT;
  if(!layout){try{layout=await (await fetch('/layout')).json();}catch{layout={focus:'daily_review',top_left:{image:'card-agenda',data:{title:'Agent CRM'}},top_right:{image:'actions-list',data:{}},bottom_left:{image:'timeline-feed',data:{}},bottom_right:{image:'pipeline-mini',data:{}}};}}
  const keys=['top_left','top_right','bottom_left','bottom_right'];
  el.innerHTML=(await Promise.all(keys.map(async k=>`<section class="q"><h2>${titles[k]}</h2>${await baseSvg(layout[k]?.image,layout[k]?.data)}${details(layout[k]?.data)}</section>`))).join('');
}
refresh(); setInterval(refresh,5000);
