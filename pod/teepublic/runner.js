(async function(item){
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 window.alert=m=>{window.__alerts=(window.__alerts||[]).concat([m]);};
 window.__st='start';
 try{
 const single=[...document.querySelectorAll('h3')].find(e=>e.offsetParent&&e.innerText.trim()=='Single File Upload'); if(single){single.click(); await sleep(1500);}
 const b=await (await fetch(item.url)).blob();
 const dt=new DataTransfer(); dt.items.add(new File([b],item.folder+'.png',{type:'image/png'}));
 const inp=document.querySelector('#jsUploaderFileInput, input.m-uploader__dropzone-input'); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true}));
 window.__st='uploading';
 for(let i=0;i<60;i++){ await sleep(1000); const t=document.querySelector('#design_design_title'); if(t&&t.offsetParent&&document.querySelector('[name="design[preview_file_info_attributes][width]"]').value) break; }
 await sleep(4000);
 const set=(el,v)=>{el.focus(); el.value=v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); el.blur();};
 set(document.querySelector('#design_design_title'),item.title);
 set(document.querySelector('#design_design_description'),item.desc);
 set(document.querySelector('#design_primary_tag'),item.main);
 const ti=document.querySelector('#secondary_tags input.taggle_input');
 for(const t of item.tags){ti.focus(); ti.value=t; ti.dispatchEvent(new Event('input',{bubbles:true})); ['keydown','keyup'].forEach(ty=>ti.dispatchEvent(new KeyboardEvent(ty,{bubbles:true,key:'Enter',keyCode:13,which:13})));}
 ti.blur();
 const cf=document.querySelector('input[name="design[content_flag]"][value="false"]'); if(cf&&!cf.checked) cf.click();
 const tm=document.querySelector('input[name="terms"]'); if(tm&&!tm.checked) tm.click();
 const dark=new Set(['1','31','19','7','14','18','129','67','24','11','2','27','116','9','8','48']);
 document.querySelectorAll('input[name="additional_colors[]"]').forEach(c=>{const want=dark.has(c.value); if(c.checked!==want) c.click();});
 document.querySelectorAll('.dd-container').forEach(dd=>{const opts=[...dd.querySelectorAll('.dd-option')]; const opt=opts.find(a=>a.innerText.trim()=='Black')||opts.find(a=>a.innerText.trim()=='Black/White'); if(opt){dd.querySelector('.dd-select').click(); opt.click();}});
 await sleep(2000);
 window.__st='publishing tags='+document.querySelectorAll('#secondary_tags .taggle_text').length;
 const f=document.querySelector('#design_design_title').form; const h=document.createElement('input'); h.type='hidden'; h.name='commit'; h.value='publish'; f.appendChild(h); HTMLFormElement.prototype.submit.call(f); // the site's async publish handler stalls in background tabs
 }catch(e){window.__st='ERR '+e;}
})
