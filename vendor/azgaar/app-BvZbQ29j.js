import{i as e}from"./rolldown-runtime-COiEfhsA.js";import{C as t,D as n,E as r,T as i,_ as a,c as o,d as s,f as c,g as l,i as u,n as d,o as f,p,r as m,t as h,w as ee,y as te}from"./index-CH0Rm5id.js";import{$ as ne,A as re,B as ie,Cn as ae,E as oe,Et as se,F as g,H as ce,J as le,K as ue,R as de,Sn as fe,St as pe,T as me,U as he,V as ge,W as _,_t as _e,a as ve,an as ye,b as be,c as v,cn as xe,dn as y,f as Se,fn as Ce,ft as we,g as Te,h as Ee,i as De,m as Oe,n as b,o as ke,on as Ae,p as je,pn as Me,pt as x,r as Ne,s as Pe,st as Fe,t as Ie,un as Le,w as Re,wt as ze,xn as Be,y as Ve,yn as He}from"./options-model-DSwdyILQ.js";import{_ as Ue,b as We,h as Ge,i as Ke,o as qe,s as Je,t as S,u as Ye,v as Xe,x as Ze}from"./pack-generator-D0TDHy_n.js";import{_ as Qe,a as $e,d as C,i as et,p as tt,u as nt,y as rt}from"./notices-DuUY2bWd.js";import{G as it,J as at,K as ot,M as st,P as ct,X as lt,_t as ut,c as dt,ct as ft,i as pt,m as mt,n as ht,q as gt,r as _t,t as w,xt as vt,yt}from"./layers-BiK81IJP.js";import{A as bt,D as T,E,S as xt,T as D,_ as O,a as St,b as Ct,d as k,f as wt,g as Tt,k as Et,l as A,p as Dt,r as Ot,t as kt,u as At,w as jt,x as Mt}from"./file-utils-CMOqg3zZ.js";import{t as Nt}from"./min-CCch3uox.js";import{i as Pt,u as Ft}from"./draw-heightmap-2BBqEGMf.js";import{a as It,l as Lt,n as Rt,o as zt,s as Bt,t as Vt}from"./color-utils-DJ0cQpfe.js";import{D as j,a as Ht,i as M,r as N,s as Ut,t as Wt,z as P}from"./node-utils-CzHgusJz.js";import{t as Gt}from"./drag-CxS08taJ.js";import{r as Kt}from"./highlight-CbbCM9IR.js";import{n as qt,r as Jt,t as F}from"./dialog-B4UlRHjQ.js";import{n as Yt,t as Xt}from"./environment-BDBII_BV.js";import{a as Zt,i as Qt,o as I,t as $t}from"./tooltips-BauP9Je3.js";import{t as L}from"./controllers-5yEnOQR8.js";import{t as R}from"./grid-generator-BNkcYyn4.js";import{a as z,n as en,o as tn,r as nn,s as rn,t as an}from"./production-generator-CMJnVToA.js";import{S as on,d as sn,f as cn,n as ln,s as un}from"./units-BeJ2915m.js";import{n as dn,t as fn}from"./map-history-DTozh336.js";import{t as pn}from"./graph-override-BysAnf1h.js";import{t as mn}from"./notes-Cq-VWWql.js";import{i as hn,o as gn}from"./fonts-U-jBQsbM.js";import{t as _n}from"./file-name-CjjRnvM3.js";import{t as vn}from"./platform-DeOWm8S8.js";import{i as yn,n as bn,r as xn,s as Sn,t as B}from"./services-BgYKPvfR.js";import{c as V,d as Cn,i as wn,l as Tn,n as En,o as Dn,r as On,s as kn,t as An,u as jn}from"./zoom-DfONK1bt.js";import{a as Mn,n as Nn,r as Pn,t as Fn}from"./canvas-DXl8m4_N.js";import{t as In}from"./added-labels-DR1_R6_c.js";import{t as Ln}from"./measurers-generator-DazKvylb.js";import{t as Rn}from"./biomes-generator-BSG4vdrc.js";import{t as zn}from"./heightmap-generator-BHZ5a9hR.js";import{t as Bn}from"./ice-generator-CUUCKVhp.js";import{t as Vn}from"./temperature-generator-DTF5CG3E.js";import{t as Hn}from"./journeys-generator-CNtl_97C.js";import{o as Un,r as Wn,t as H}from"./styles-BAzlhwvr.js";import{t as Gn}from"./map-restoration-BwZj8Ci0.js";globalThis.grid={},globalThis.pack={};function Kn(e,t){this._basis=new Je(e),this._beta=t}Kn.prototype={lineStart:function(){this._x=[],this._y=[],this._basis.lineStart()},lineEnd:function(){var e=this._x,t=this._y,n=e.length-1;if(n>0)for(var r=e[0],i=t[0],a=e[n]-r,o=t[n]-i,s=-1,c;++s<=n;)c=s/n,this._basis.point(this._beta*e[s]+(1-this._beta)*(r+c*a),this._beta*t[s]+(1-this._beta)*(i+c*o));this._x=this._y=null,this._basis.lineEnd()},point:function(e,t){this._x.push(+e),this._y.push(+t)}};var qn=(function e(t){function n(e){return t===1?new Je(e):new Kn(e,t)}return n.beta=function(t){return e(+t)},n})(.85);globalThis.options=b.getDefaultOptions();var Jn=new Map([[`texture`,{label:u(`Texture`),shortcut:`KeyX`}],[`heightmap`,{label:u(`Heightmap`),shortcut:`KeyH`}],[`lakes`,{label:u(`Lakes`),shortcut:`KeyQ`}],[`biomes`,{label:u(`Biomes`),shortcut:`KeyB`}],[`cells`,{label:u(`Cells`),shortcut:`KeyE`}],[`grid`,{label:u(`Grid`),shortcut:`Semicolon`,hint:`; (${u(`semicolon`)})`}],[`coordinates`,{label:u(`Coordinates`),shortcut:`KeyO`}],[`compass`,{label:u(`Wind Rose`),shortcut:`KeyW`}],[`rivers`,{label:u(`Rivers`),shortcut:`KeyV`}],[`relief`,{label:u(`Relief`),shortcut:`KeyF`}],[`religions`,{label:u(`Religions`),shortcut:`KeyR`}],[`cultures`,{label:u(`Cultures`),shortcut:`KeyC`}],[`states`,{label:u(`States`),shortcut:`KeyS`}],[`provinces`,{label:u(`Provinces`),shortcut:`KeyP`}],[`zones`,{label:u(`Zones`),shortcut:`KeyZ`}],[`borders`,{label:u(`Borders`),shortcut:`KeyD`}],[`routes`,{label:u(`Routes`),shortcut:`KeyU`}],[`temperature`,{label:u(`Temperature`),shortcut:`KeyT`}],[`ice`,{label:u(`Ice`),shortcut:`KeyJ`}],[`goods`,{label:u(`Goods`),shortcut:`KeyG`}],[`markets`,{label:u(`Markets`)}],[`trade`,{label:u(`Trade`),shortcut:`Backquote`,hint:`\` (${u(`backtick`)})`}],[`precipitation`,{label:u(`Precipitation`),shortcut:`KeyA`}],[`population`,{label:u(`Population`),shortcut:`KeyN`}],[`emblems`,{label:u(`Emblems`),shortcut:`KeyY`}],[`burgIcons`,{label:u(`Icons`),shortcut:`KeyI`}],[`labels`,{label:u(`Labels`),shortcut:`KeyL`}],[`military`,{label:u(`Military`),shortcut:`KeyM`}],[`markers`,{label:u(`Markers`),shortcut:`KeyK`}],[`journeys`,{label:u(`Journeys`)}],[`rulers`,{label:u(`Rulers`),shortcut:`Equal`,hint:`= (${u(`equal sign`)})`}],[`scaleBar`,{label:u(`Scale Bar`),shortcut:`Slash`,hint:`/ (${u(`slash sign`)})`}],[`vignette`,{label:u(`Vignette`),shortcut:`BracketLeft`,hint:`[ (${u(`left square bracket`)})`}]]),Yn={coastline:u(`Coastline`),fogging:u(`Fogging`),landmass:u(`Landmass`),legend:u(`Legend`),ocean:u(`Ocean`)};function Xn(e){return e===`map`?u(`Map`):Jn.get(e)?.label??Yn[e]??e.charAt(0).toUpperCase()+e.slice(1)}function Zn({label:e,shortcut:t}){let n=t?.startsWith(`Key`)?t.slice(3).toLowerCase():``,r=n?e.toLowerCase().indexOf(n):-1;return r<0?e:`${e.slice(0,r)}<u>${e[r]}</u>${e.slice(r+1)}`}var Qn={political:u(`Political map`),cultural:u(`Cultural map`),religions:u(`Religions map`),provinces:u(`Provinces map`),biomes:u(`Biomes map`),heightmap:u(`Heightmap`),physical:u(`Physical map`),poi:u(`Places of interest`),goods:u(`Goods map`),trade:u(`Trade animation`),military:u(`Military map`),emblems:u(`Emblems`),landmass:u(`Pure landmass`)},$n=e=>[...Jn].find(([,t])=>t.shortcut===e)?.[0],er=`
  <div class="head">
    <p data-tip="${u(`Select a map layers preset`)}">${u(`Layers preset`)}:</p>
    <select data-tip="${u(`Select a map layers preset`)}" id="layersPreset">
      ${Object.entries(Qn).map(([e,t])=>`<option value="${e}">${t}</option>`).join(``)}
      <option hidden value="custom">${u(`Custom (not saved)`)}</option>
    </select>
    <button
      id="savePresetButton"
      data-tip="${u(`Click to save displayed layers as a new preset`)}"
      class="icon-plus sideButton"
      style="display: none"
    ></button>
    <button
      id="removePresetButton"
      data-tip="${u(`Remove`)}"
      class="icon-minus sideButton"
      style="display: none"
    ></button>
    <button id="layersOrderButton" data-tip="${u(`Change the layer order`)}" class="icon-sort-alt-down sideButton"></button>
  </div>
  <div data-tip="${m(u(`Click to toggle the layer`),u(`Ctrl + click to edit layer style`))}" id="mapLayers"></div>
  <div class="tip">${u(`Click to toggle the layer`)}. ${u(`Ctrl + click to edit layer style`)}</div>
  <div id="viewMode" data-tip="${u(`Set view mode`)}">
    <p>${u(`View mode`)}:</p>
    <button data-tip="${u(`Standard view mode for editing the map`)}" id="viewStandard" class="pressed">
      ${u(`Standard`)}
    </button>
    <button
      data-tip="${m(u(`Map presentation in 3D scene`),u(`Works best for heightmap`),u(`Cannot be used for editing`))}"
      id="viewMesh"
    >
      ${u(`3D scene`)}
    </button>
    <button data-tip="${m(u(`Project map on globe`),u(`Cannot be used for editing`))}" id="viewGlobe">${u(`Globe`)}</button>
  </div>
`;N(`layersContent`).innerHTML=er;function tr(){N(`mapLayers`).replaceChildren(...w.all.flatMap(e=>{let t=Jn.get(e.id);if(!t)return[];let n=document.createElement(`button`);return n.dataset.layer=e.id,n.dataset.tip=m(u(`Toggle {{- layer}}`,{layer:t.label}),u(`Ctrl + click to edit layer style`)),t.shortcut&&(n.dataset.shortcut=t.hint??t.shortcut.replace(`Key`,``)),n.innerHTML=Zn(t),n.classList.toggle(`buttonoff`,!w.isOn(e.id)),[n]}))}N(`mapLayers`).addEventListener(`click`,e=>{let t=e.target.closest(`button`)?.dataset.layer;if(t&&w.has(t)){if(nt(e)&&!options.map.viewOnly)return void L.StyleEditor.open(t);w.toggle(t)}}),N(`layersOrderButton`).addEventListener(`click`,()=>void L.LayersOrder.open()),w.subscribe(tr),w.subscribe(()=>ut.renderNow());var nr;w.subscribe(()=>{M(`canvas3d`)&&(clearTimeout(nr),nr=window.setTimeout(()=>void L.View3d.update(),400))}),tr();var rr=`
  <div class="head">
    <p data-tip="${u(`Select a style preset. State labels may required regeneration if font is changed`)}">${u(`Preset`)}:</p>
    <button type="button" id="stylePreset" data-tip="${u(`Click to select a style preset`)}"></button>
    <button id="addStyleButton" data-tip="${u(`Click to save current style as a new preset`)}" class="icon-plus sideButton"></button>
  </div>
  <div class="head">
    <p data-tip="${u(`Select an element to edit its style`)}">${u(`Element`)}:</p>
    <select data-tip="${u(`Select an element to edit its style`)}" id="styleElementSelect"></select>
    <button id="styleElementTreeButton" data-tip="${u(`Browse all elements and their groups`)}" class="icon-sitemap sideButton"></button>
  </div>
  <div class="head group-row" style="display: none">
    <p data-tip="${u(`Select element group`)}">${u(`Group`)}:</p>
    <select data-tip="${u(`Select element group`)}" id="styleGroupSelect"></select>
  </div>
  <div id="styleForm"></div>
`,ir=`
  :root {
    --style-card-fill: rgba(255, 255, 255, .1);
    --style-card-head: rgba(255, 255, 255, .2);
    --style-group-line: rgba(0, 0, 0, .15);
  }
  #stylePreset { flex: 1 1 auto; min-width: 0; height: 1.6em; margin: 0; padding: 0 .3em; font-size: smaller; display: flex; align-items: center; gap: .4em; background: #fff; color: #000; border: .5px solid #dbdfe6; border-top-color: #abadb3; border-radius: .5px; text-transform: capitalize; cursor: pointer; }
  #stylePreset > span { flex: 1 1 auto; min-width: 0; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #stylePreset::after { content: "▾"; opacity: .6; }
  #styleForm { margin-top: .4em; }
  #styleForm .banner { color: darkred; font-weight: 700; margin: .3em 0; }
  #styleForm .banner a { cursor: pointer; text-decoration: underline; }
  #styleForm .pick { margin: 0; flex: 1 1 0; display: flex; align-items: center; gap: .4em; padding: 0.1em .4em; background: #ffffff; font-size: smaller; }
  #styleForm .pick::after { content: "▾"; margin-left: auto; opacity: .6; }
  #styleForm .pick > svg { flex: none; width: 1.4em; height: 1.4em; overflow: visible; }
  #styleForm .reset { flex: none; visibility: hidden; border: 0; background: none; box-shadow: none; color: var(--dark-solid); padding: 0 .2em; margin: 0; cursor: pointer; }
  #styleForm .changed .reset { visibility: visible; }
  #styleForm .reset.blank { visibility: hidden; }
  #styleForm details[data-section] > summary:has(> .gate.changed) { box-shadow: inset 3px 0 0 var(--dark-solid); }
  #styleForm summary > .preview { display: flex; height: 1.6em; } /* reserved, so every header is the same height */
  #styleForm summary > .preview > .sample { font-size: 1.25em; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #styleForm summary > .preview > .chip { flex: none; width: 3em; height: 1.6em; overflow: visible; }
  #styleForm summary > .preview > .ramp { flex: none; width: 2.6em; height: .9em; border: 1px solid #333; border-radius: 3px; }
  #styleForm summary > .preview > .tex { flex: none; width: 1.8em; height: 1.5em; border: 1px solid #333; border-radius: 3px; background-size: cover; background-position: center; }
  #styleForm summary > .preview > .icon { flex: none; display: flex; }
  #styleForm summary > .preview > .icon > svg { width: 1.5em; height: 1.5em; overflow: visible; }
  #styleForm summary > .preview > .off { opacity: .45; }
`;N(`styleContent`).innerHTML=rr;var ar=document.createElement(`style`);ar.textContent=ir,document.head.append(ar);var or=`
  <p>${u(`Heightmap customization tools`)}:</p>
  <div id="customizeTools">
    <button data-tip="${u(`Display brushes panel`)}" id="paintBrushes">${u(`Paint Brushes`)}</button>
    <button data-tip="${u(`Template Editor`)}" id="applyTemplate" style="display: none">${u(`Template Editor`)}</button>
    <button data-tip="${u(`Image Converter`)}" id="convertImage" style="display: none">${u(`Image Converter`)}</button>
    <button data-tip="${u(`Render heightmap data as a small monochrome image`)}" id="heightmapPreview">${u(`Preview`)}</button>
    <button data-tip="${u(`Preview the heightmap in a 3D scene`)}" id="heightmap3DView">${u(`3D scene`)}</button>
  </div>
  <p>${u(`Options`)}:</p>
  <div id="customizeOptions">
    <div data-tip="${u(`Heightmap edit mode`)}">${u(`Edit mode`)}: <span id="heightmapEditMode"></span></div>
    <div data-tip="${u(`Render cells below sea level (with a height less than 20)`)}">
      <input id="renderOcean" class="checkbox" type="checkbox" />
      <label for="renderOcean" class="checkbox-label">${u(`Render ocean cells`)}</label>
    </div>
    <div data-tip="${u(`Show where water flows: arrows point downhill, hatching marks depressions that get filled, blue hatching marks the ones deep enough to become lakes`)}">
      <input id="showDrainage" class="checkbox" type="checkbox" />
      <label for="showDrainage" class="checkbox-label">${u(`Show drainage`)}</label>
    </div>
    <div
      id="allowErosionBox"
      data-tip="${u(`Regenerate rivers and allow water flow to change heights and form new lakes. Recommended`)}"
    >
      <input id="allowErosion" class="checkbox" type="checkbox" />
      <label for="allowErosion" class="checkbox-label">${u(`Allow water erosion`)}</label>
    </div>
    <div
      data-tip="${u(`Maximum number of iterations to fill depressions. Increase if rivers end without reaching a lake or the sea`)}"
    >
      <div>${u(`Maximum depression filling iterations`)}:</div>
      <input
        id="resolveDepressionsStepsInput"
        data-option="resolveDepressionsSteps"
        type="range"
        min="0"
        max="500"
        value="250"
      />
      <input
        id="resolveDepressionsStepsOutput"
        data-option="resolveDepressionsSteps"
        type="number"
        min="0"
        max="1000"
        value="250"
      />
    </div>
    <div data-tip="${u(`Depression depth needed to form a new lake. Increase to reduce the number of generated lakes`)}">
      <div>${u(`Depression depth threshold`)}:</div>
      <input
        id="lakeElevationLimitInput"
        data-option="lakeElevationLimit"
        type="range"
        min="0"
        max="80"
        value="20"
      />
      <input
        id="lakeElevationLimitOutput"
        data-option="lakeElevationLimit"
        type="number"
        min="0"
        max="80"
        value="20"
      />
    </div>
  </div>
  <p>${u(`Statistics`)}:</p>
  <div>
    <span>${u(`Land cells`)}: </span><span id="landmassCounter">0</span>
    <span style="margin-left: 0.9em">${u(`Mean height`)}: </span><span id="landmassAverage">0</span>
  </div>
  <p>${u(`Cell info`)}:</p>
  <div>
    <span>${u(`Coord`)}: </span><span id="heightmapInfoX"></span>/<span id="heightmapInfoY"></span><br />
    <span>${u(`Cell`)}: </span><span id="heightmapInfoCell"></span><br />
    <span>${u(`Height`)}: </span><span id="heightmapInfoHeight"></span>
  </div>
`;N(`heightmapMenu`).innerHTML=or;var sr=(e,t,n)=>P(`#${e}`).transition().duration(n).style(`opacity`,String(t));function cr(){sr(`loading`,1,200),sr(`optionsContainer`,0,100),sr(`tooltip`,0,200)}function lr(){sr(`loading`,0,3e3),sr(`optionsContainer`,1,2e3),sr(`tooltip`,1,3e3)}var ur=e(Ue());function dr(e){if(e)options.map.seed=e;else{let e=!fn.length,t=new URL(window.location.href).searchParams.get(`seed`);if(e&&t){let e=new URL(window.location.href).searchParams.get(`from`)===`MFCG`&&t.length===13;options.map.seed=e?t.slice(0,-4):t}else options.map.seed=xt()}Math.random=(0,ur.default)(options.map.seed)}function fr(){let e=N(`seedInput`).value;e===options.map.seed?I(u(`The current map already has this seed`),!1,`error`):Mo({seed:e})}function pr(){let e=fn.map((e,t)=>{let n=new Date(e.created).toLocaleTimeString(),r=`<i data-tip="${u(`Click to generate a map with this seed`)}" data-index="${t}" class="icon-history optionsSeedRestore"></i>`;return`<li>${u(`Seed: {{seed}} {{- restore}}. Size: {{width}}x{{height}}. Template: {{template}}. Created: {{created}}`,{seed:e.seed,restore:r,width:e.width,height:e.height,template:e.template,created:n})}</li>`}),t=F.message({title:u(`Seed history`),message:`<ol style="margin: 0; padding-left: 1.5em">${e.join(``)}</ol>`});for(let e of t.querySelectorAll(`.optionsSeedRestore`))e.addEventListener(`click`,()=>mr(Number(e.dataset.index)))}function mr(e){let{seed:t,width:n,height:r,template:i}=fn[e];b.set(e=>e.generation.template=i),v.has(`template`)&&v.clear(`template`),Mo({seed:t,width:n,height:r})}function hr(){w.init(),_r(),window.addEventListener(`resize`,vr),window.addEventListener(`vite:preloadError`,br),xr(),Sr(),yr(),!Yt()&&!Xt()&&(window.onbeforeunload=()=>u(`Are you sure you want to navigate away?`)),Xt()&&wr()}var gr=[[`#optionsTrigger`,null,u(`Click to show the Menu`)],[`#regenerate`,u(`New Map!`),u(`Click to generate a new map`)],[`#options .drag-trigger`,null,u(`Drag to move the Menu`)],[`#optionsHide`,null,u(`Click to hide the Menu`)],[`#layersTab`,u(`Layers`),u(`Click to change map layers`)],[`#styleTab`,u(`Style`),u(`Click to open style editor`)],[`#optionsTab`,u(`Options`),u(`Click to change generation and UI options`)],[`#toolsTab`,u(`Tools`),u(`Click to open tools menu`)],[`#aboutTab`,u(`About`),u(`Click to see Generator info`)],[`#newMapButton`,u(`New Map`),u(`Generate a new map based on options`)],[`#exportButton`,u(`Export`),u(`Select format to download image or export map data`)],[`#saveButton`,u(`Save`),u(`Save fully-functional map file`)],[`#loadButton`,u(`Load`),u(`Load fully-functional map (.map or .gz formats)`)],[`#zoomReset`,u(`Zoom Out`,{context:`button`}),u(`Reset map zoom`)],[`#searchButton`,u(`Search`,{context:`button`}),u(`Search map and commands`)],[`#heightmapFinalize > div`,null,u(`Drag to move the pane`)],[`#finalizeHeightmap`,u(`Exit Customization`),u(`Finalize the heightmap and exit the edit mode`)],[`#assistantBubble`,null,u(`Azgaar Assistant`)],[`#mapOverlay`,u(`Drop a map file to open`),null],[`#tourPromptButton`,null,u(`Take an interactive tour of the map generator`)]];function _r(){for(let[e,t,n]of gr){let r=document.querySelector(e);r&&(t!==null&&(r.textContent=t),n!==null&&(r.dataset.tip=n))}M(`assistantBubble`)?.setAttribute(`aria-label`,u(`Azgaar Assistant`)),document.querySelector(`#tourPromptButton button`)?.setAttribute(`aria-label`,u(`Launch UI Tour`));let e=M(`tooltip`);e&&(e.dataset.main=u(`Click the arrow button for options. Zoom in to see the map in details`));let t=M(`loading-text`)?.firstChild;t&&(t.textContent=u(`Loading`).toUpperCase())}function vr(){b.set(e=>{v.rolls(`mapWidth`)&&window.innerWidth>0&&(e.generation.graph.width=window.innerWidth),v.rolls(`mapHeight`)&&window.innerHeight>0&&(e.generation.graph.height=window.innerHeight)}),Pn()}function yr(){let e=M(`assistantBubble`);e&&(e.addEventListener(`click`,()=>L.Assistant.toggle()),e.addEventListener(`mouseover`,Qt))}function br(){navigator.onLine?F.confirm({title:u(`New version released`),message:`${u(`This part of the app failed to load because a new version was released while the page was open.`)}<br>${m(u(`Reload the page to get the new version`),u(`If you have unsaved changes, save the map first`))}`,confirm:u(`Reload`),cancel:u(`Not now`),onConfirm:()=>{window.onbeforeunload=null,location.reload()}}):F.message({title:u(`You are offline`),message:u(`This part of the app was not downloaded before the connection was lost. Reconnect and try again`)})}function xr(){let e=()=>N(`mapOverlay`);document.addEventListener(`dragover`,t=>{t.stopPropagation(),t.preventDefault(),e().style.display=null}),document.addEventListener(`dragleave`,()=>{e().style.display=`none`}),document.addEventListener(`drop`,t=>{t.stopPropagation(),t.preventDefault();let n=e();n.style.display=`none`;let r=t.dataTransfer?.items;if(r?.length!==1)return;let i=r[0].getAsFile();if(i){if(!i.name.endsWith(`.map`)&&!i.name.endsWith(`.gz`))return F.message({title:u(`Invalid file format`),message:u(`Please upload a map file (.map or .gz formats) you have previously downloaded`)});n.style.display=null,n.innerHTML=`${u(`Uploading`)}<span>.</span><span>.</span><span>.</span>`,F.closeAll(),B.Load.uploadMap(i,()=>{n.style.display=`none`,n.innerHTML=u(`Drop a map file to open`)})}})}function Sr(){let e=`fmg-tour-prompt-count`,t=Number.parseInt(localStorage.getItem(e)||`0`,10);if(t>=2)return;let n=M(`tourPromptButton`);n&&(n.style.display=`flex`,n.addEventListener(`click`,()=>{B.UiTour.start(),localStorage.setItem(e,`2`)}),localStorage.setItem(e,String(t+1)))}function Cr(){return!location.hostname&&(F.message({title:u(`Loading error`),width:`28em`,message:u(`Fantasy Map Generator cannot run serverless. Follow the {{- instructions}} on how you can easily run a local web-server`,{instructions:`<a href="https://github.com/Azgaar/Fantasy-Map-Generator/wiki/Run-FMG-locally" target="_blank">${u(`instructions`)}</a>`})}),!0)}function wr(){M(`getAppButton`)?.remove(),M(`saveToDropboxButton`)?.remove(),M(`loadFromDropbox`)?.remove()}var Tr=class{name;steps;constructor(e,t){this.name=e,this.steps=t}async run(e){h.group(this.name),h.time(this.name);let t=performance.now();try{for(let t of this.steps){h.time(t.id);let n=performance.now();try{await t.run(e)}catch(e){let n=c(e);throw Error(`${this.name} failed at step "${t.id}": ${n}`,{cause:e})}finally{h.timeEnd(t.id),performance.measure(t.id,{start:n,detail:this.name})}}}finally{h.timeEnd(this.name),performance.measure(this.name,{start:t}),h.groupEnd()}}},Er=new class{config;constructor(){this.config={invasion:{quantity:2,generate:e=>this.addInvasion(e)},rebels:{quantity:1.5,generate:e=>this.addRebels(e)},proselytism:{quantity:1.6,generate:e=>this.addProselytism(e)},crusade:{quantity:1.6,generate:e=>this.addCrusade(e)},disease:{quantity:1.4,generate:e=>this.addDisease(e)},disaster:{quantity:1,generate:e=>this.addDisaster(e)},eruption:{quantity:1,generate:e=>this.addEruption(e)},avalanche:{quantity:.8,generate:e=>this.addAvalanche(e)},fault:{quantity:1,generate:e=>this.addFault(e)},flood:{quantity:1,generate:e=>this.addFlood(e)},tsunami:{quantity:1,generate:e=>this.addTsunami(e)}}}rename(e,t){this.living(e).name=y(t)}recolor(e,t){this.living(e).color=Bt(t)}setType(e,t){this.living(e).type=y(t)}setHidden(e,t){let n=this.living(e);t?n.hidden=!0:delete n.hidden}add(e,t,n){let r=pack.zones.length?Math.max(...pack.zones.map(e=>e.i))+1:0,i={i:r,name:y(e),type:y(t),color:`url(#hatch${r%42})`,cells:[],tags:[]};return pack.zones.push(i),this.setCells(r,n),r}setCells(e,t){let n=pack.cells.i.length;if(!Array.isArray(t)||!t.length||t.some(e=>!Number.isInteger(e)||e<0||e>=n))throw Error(`The cells must be a non-empty list of cell ids from 0 to ${n-1}`);this.living(e).cells=[...new Set(t)]}setPopulation(e,t,n){let r=new Set(this.living(e).cells);he.setArea(he.landCells(e=>r.has(e)),he.burgIds(e=>r.has(e.cell)),t,n)}remove(e){this.living(e),pack.zones=pack.zones.filter(t=>t.i!==e)}living(e){let t=pack.zones.find(({i:t})=>t===e);if(!t)throw Error(`Zone ${e} does not exist`);return t}regenerate(e=1){this.generate(e)}generate(e=1){let t=new Uint8Array(pack.cells.i.length);pack.zones=[],Object.values(this.config).forEach(n=>{let r=n.quantity*e,i=Mt(r,r/2,0,100);for(;i--;)n.generate(t)});for(let e of pack.zones)e&&!e.tags&&(e.tags=[])}addInvasion(e){let{cells:t,states:n}=pack,r=n.filter(e=>e.i&&!e.removed&&e.campaigns).flatMap(e=>e.campaigns).filter(e=>!e.end);if(!r.length)return;let{defender:i,attacker:a}=D(r),o=t.i.filter(n=>e[n]||t.state[n]!==i?!1:t.c[n].some(e=>t.state[e]===a)),s=D(o);if(s===void 0)return;let c=[],l=[s],u=E(5,30);for(;l.length;){let n=O(.4)?l.shift():l.pop();if(c.push(n),c.length>=u)break;t.c[n].forEach(n=>{e[n]||t.state[n]===i&&(e[n]=1,l.push(n))})}let d=T({Invasion:5,Occupation:4,Conquest:3,Incursion:2,Intervention:2,Assault:1,Foray:1,Intrusion:1,Irruption:1,Offensive:1,Pillaging:1,Plunder:1,Raid:1,Skirmishes:1}),f=`${k(n[a].name)} ${d}`;pack.zones.push({i:pack.zones.length,name:f,type:`Invasion`,cells:c,color:`url(#hatch1)`})}addRebels(e){let{cells:t,states:n}=pack,r=D(n.filter(e=>e.i&&!e.removed&&e.neighbors?.some(Boolean)));if(!r)return;let i=D(r.neighbors.filter(e=>e&&!n[e].removed));if(!i)return;let a=[],o=[],s=t.i.find(e=>t.state[e]===r.i&&t.c[e].some(e=>t.state[e]===i));s&&o.push(s);let c=E(10,30);for(;o.length;){let n=o.shift();if(a.push(n),a.length>=c)break;t.c[n].forEach(n=>{e[n]||t.state[n]===r.i&&(e[n]=1,(n%4==0||t.c[n].some(e=>t.state[e]===i))&&o.push(n))})}let l=T({Rebels:5,Insurrection:2,Mutineers:1,Insurgents:1,Rebellion:1,Renegades:1,Revolters:1,Revolutionaries:1,Rioters:1,Separatists:1,Secessionists:1,Conspiracy:1}),u=`${k(n[i].name)} ${l}`;pack.zones.push({i:pack.zones.length,name:u,type:`Rebels`,cells:a,color:`url(#hatch3)`})}addProselytism(e){let{cells:t,religions:n}=pack,r=n.filter(e=>e.i&&!e.removed&&e.type===`Organized`),i=D(r);if(!i)return;let a=t.i.filter(e=>t.h[e]>=20&&t.pop[e]&&t.religion[e]!==i.i&&t.c[e].some(e=>t.religion[e]===i.i)),o=D(a);if(!o)return;let s=t.religion[o],c=[],l=[o],u=E(10,30);for(;l.length;){let n=l.shift();if(c.push(n),c.length>=u)break;t.c[n].forEach(n=>{e[n]||t.religion[n]===s&&(t.h[n]<20||!t.pop[n]||(e[n]=1,l.push(n)))})}let d=`${k(i.name.split(` `)[0])} Proselytism`;pack.zones.push({i:pack.zones.length,name:d,type:`Proselytism`,cells:c,color:`url(#hatch6)`})}addCrusade(e){let{cells:t,religions:n}=pack,r=n.filter(e=>!e.removed&&e.type===`Heresy`);if(!r.length)return;let i=D(r),a=t.i.filter(n=>!e[n]&&t.religion[n]===i.i);if(!a.length)return;for(let t of a)e[t]=1;let o=`${k(i.name.split(` `)[0])} Crusade`;pack.zones.push({i:pack.zones.length,name:o,type:`Crusade`,cells:Array.from(a),color:`url(#hatch6)`})}addDisease(e){let{cells:t,burgs:n}=pack,r=D(n.filter(t=>!e[t.cell]&&t.i&&!t.removed));if(!r)return;let i=[],a=[],o=E(20,40),s=new se;for(s.push({e:r.cell,p:0},0);s.length;){let n=s.pop();(t.burg[n.e]||t.pop[n.e])&&i.push(n.e),e[n.e]=1,t.c[n.e].forEach(e=>{let t=_.getRoute(n.e,e)?5:100,r=n.p+t;r>o||(!a[e]||r<a[e])&&(a[e]=r,s.push({e,p:r},r))})}let c=this.getDiseaseName(`color`),l=this.getDiseaseName(`animal`),u=this.getDiseaseName(`adjective`),d=T({color:2,animal:1,adjective:1}),f=`${d===`color`?c:d===`animal`?l:u} ${T({Fever:5,Plague:3,Cough:3,Flu:2,Pox:2,Cholera:2,Typhoid:2,Leprosy:1,Smallpox:1,Pestilence:1,Consumption:1,Malaria:1,Dropsy:1})}`;pack.zones.push({i:pack.zones.length,name:f,type:`Disease`,cells:i,color:`url(#hatch12)`})}getDiseaseName(e){return D(e===`color`?[`Amber`,`Azure`,`Black`,`Blue`,`Brown`,`Crimson`,`Emerald`,`Golden`,`Green`,`Grey`,`Orange`,`Pink`,`Purple`,`Red`,`Ruby`,`Scarlet`,`Silver`,`Violet`,`White`,`Yellow`]:e===`animal`?[`Ape`,`Bear`,`Bird`,`Boar`,`Cat`,`Cow`,`Deer`,`Dog`,`Fox`,`Goat`,`Horse`,`Lion`,`Pig`,`Rat`,`Raven`,`Sheep`,`Spider`,`Tiger`,`Viper`,`Wolf`,`Worm`,`Wyrm`]:[`Blind`,`Bloody`,`Brutal`,`Burning`,`Deadly`,`Fatal`,`Furious`,`Great`,`Grim`,`Horrible`,`Invisible`,`Lethal`,`Loud`,`Mortal`,`Savage`,`Severe`,`Silent`,`Unknown`,`Venomous`,`Vicious`])}addDisaster(e){let{cells:t,burgs:n}=pack,r=D(n.filter(t=>!e[t.cell]&&t.i&&!t.removed));if(!r)return;e[r.cell]=1;let i=[],a=[],o=E(5,25),s=new se;for(s.push({e:r.cell,p:0},0);s.length;){let n=s.pop();(t.burg[n.e]||t.pop[n.e])&&i.push(n.e),e[n.e]=1,t.c[n.e].forEach(e=>{let t=E(1,10),r=n.p+t;r>o||(!a[e]||r<a[e])&&(a[e]=r,s.push({e,p:r},r))})}let c=T({Famine:5,Drought:3,Earthquake:3,Dearth:1,Tornadoes:1,Wildfires:1,Storms:1,Blight:1}),l=`${k(r.name)} ${c}`;pack.zones.push({i:pack.zones.length,name:l,type:`Disaster`,cells:i,color:`url(#hatch5)`})}addEruption(e){let{cells:t,markers:n}=pack,r=n.find(t=>t.type===`volcanoes`&&!e[t.cell]);if(!r)return;e[r.cell]=1,r.note&&=r.note.replace(`Active volcano`,`Erupting volcano`);let i=r.name?`${r.name.replace(` Volcano`,``)} Eruption`:`Volcano Eruption`,a=[],o=[r.cell],s=E(10,30);for(;o.length;){let n=O(.5)?o.shift():o.pop();if(a.push(n),a.length>=s)break;t.c[n].forEach(n=>{e[n]||t.h[n]<20||(e[n]=1,o.push(n))})}pack.zones.push({i:pack.zones.length,name:i,type:`Eruption`,cells:a,color:`url(#hatch7)`})}addAvalanche(e){let{cells:t}=pack,n=t.i.filter(n=>!e[n]&&_.isConnected(n)&&t.h[n]>=70);if(!n.length)return;let r=D(n);e[r]=1;let i=[],a=[r],o=E(3,15);for(;a.length;){let n=O(.3)?a.shift():a.pop();if(i.push(n),i.length>=o)break;t.c[n].forEach(n=>{e[n]||t.h[n]<65||(e[n]=1,a.push(n))})}let s=`${k(A.getCultureShort(t.culture[r]))} Avalanche`;pack.zones.push({i:pack.zones.length,name:s,type:`Avalanche`,cells:i,color:`url(#hatch5)`})}addFault(e){let t=pack.cells,n=t.i.filter(n=>!e[n]&&t.h[n]>50&&t.h[n]<70);if(!n.length)return;let r=D(n);e[r]=1;let i=[],a=[r],o=E(3,15);for(;a.length;){let n=a.pop();if(t.h[n]>=20&&i.push(n),i.length>=o)break;t.c[n].forEach(n=>{e[n]||t.r[n]||(e[n]=1,a.push(n))})}let s=`${k(A.getCultureShort(t.culture[r]))} Fault`;pack.zones.push({i:pack.zones.length,name:s,type:`Fault`,cells:i,color:`url(#hatch2)`})}addFlood(e){let t=pack.cells,n=t.fl.filter(Boolean),r=Et(n)??0,i=((bt(n)??0)-r)/2+r,a=t.i.filter(n=>!e[n]&&t.h[n]<50&&t.r[n]&&t.fl[n]>i&&t.burg[n]);if(!a.length)return;let o=D(a);e[o]=1;let s=t.r[o],c=[],l=[o],u=E(5,30);for(;l.length;){let n=l.pop();if(c.push(n),c.length>=u)break;t.c[n].forEach(n=>{e[n]||t.h[n]<20||t.r[n]!==s||t.h[n]>50||t.fl[n]<r||(e[n]=1,l.push(n))})}let d=`${k(pack.burgs[t.burg[o]].name)} Flood`;pack.zones.push({i:pack.zones.length,name:d,type:`Flood`,cells:c,color:`url(#hatch13)`})}addTsunami(e){let{cells:t,features:n}=pack,r=t.i.filter(r=>!e[r]&&t.t[r]===-1&&n[t.f[r]].type!==`lake`);if(!r.length)return;let i=D(r);e[i]=1;let a=[],o=[i],s=E(10,30);for(;o.length;){let n=o.shift();if(t.t[n]===1&&a.push(n),a.length>=s)break;t.c[n].forEach(n=>{e[n]||t.t[n]>2||pack.features[t.f[n]].type!==`lake`&&(e[n]=1,o.push(n))})}let c=`${k(A.getCultureShort(t.culture[i]))} Tsunami`;pack.zones.push({i:pack.zones.length,name:c,type:`Tsunami`,cells:a,color:`url(#hatch13)`})}},Dr=[`Folk`,`Organized`,`Cult`,`Heresy`],Or=[`global`,`state`,`culture`],kr={Number:1,Being:3,Adjective:5,"Color + Animal":5,"Adjective + Animal":5,"Adjective + Being":5,"Adjective + Genitive":1,"Color + Being":3,"Color + Genitive":3,"Being + of + Genitive":2,"Being + of the + Genitive":1,"Animal + of + Genitive":1,"Adjective + Being + of + Genitive":2,"Adjective + Animal + of + Genitive":2},Ar=[];for(let e in kr)for(let t=0;t<kr[e];t++)Ar.push(e);var U={number:[`One`,`Two`,`Three`,`Four`,`Five`,`Six`,`Seven`,`Eight`,`Nine`,`Ten`,`Eleven`,`Twelve`],being:`Ancestor.Ancient.Avatar.Brother.Champion.Chief.Council.Creator.Deity.Divine One.Elder.Enlightened Being.Father.Forebear.Forefather.Giver.God.Goddess.Guardian.Guide.Hierarch.Lady.Lord.Maker.Master.Mother.Numen.Oracle.Overlord.Protector.Reaper.Ruler.Sage.Seer.Sister.Spirit.Supreme Being.Transcendent.Virgin`.split(`.`),animal:`Antelope.Ape.Badger.Basilisk.Bear.Beaver.Bison.Boar.Buffalo.Camel.Cat.Centaur.Cerberus.Chimera.Cobra.Cockatrice.Crane.Crocodile.Crow.Cyclope.Deer.Dog.Direwolf.Drake.Dragon.Eagle.Elephant.Elk.Falcon.Fox.Goat.Goose.Gorgon.Gryphon.Hare.Hawk.Heron.Hippogriff.Horse.Hound.Hyena.Ibis.Jackal.Jaguar.Kitsune.Kraken.Lark.Leopard.Lion.Manticore.Mantis.Marten.Minotaur.Moose.Mule.Narwhal.Owl.Ox.Panther.Pegasus.Phoenix.Python.Rat.Raven.Roc.Rook.Scorpion.Serpent.Shark.Sheep.Snake.Sphinx.Spider.Swan.Tiger.Turtle.Unicorn.Viper.Vulture.Walrus.Wolf.Wolverine.Worm.Wyvern.Yeti`.split(`.`),adjective:`Aggressive.Almighty.Ancient.Beautiful.Benevolent.Big.Blind.Blond.Bloody.Brave.Broken.Brutal.Burning.Calm.Celestial.Cheerful.Crazy.Cruel.Dead.Deadly.Devastating.Distant.Disturbing.Divine.Dying.Eternal.Ethernal.Empyreal.Enigmatic.Enlightened.Evil.Explicit.Fair.Far.Fat.Fatal.Favorable.Flying.Friendly.Frozen.Giant.Good.Grateful.Great.Happy.High.Holy.Honest.Huge.Hungry.Illustrious.Immutable.Ineffable.Infallible.Inherent.Last.Latter.Lost.Loud.Lucky.Mad.Magical.Main.Major.Marine.Mythical.Mystical.Naval.New.Noble.Old.Otherworldly.Patient.Peaceful.Pregnant.Prime.Proud.Pure.Radiant.Resplendent.Sacred.Sacrosanct.Sad.Scary.Secret.Selected.Serene.Severe.Silent.Sleeping.Slumbering.Sovereign.Strong.Sunny.Superior.Supernatural.Sustainable.Transcendent.Transcendental.Troubled.Unearthly.Unfathomable.Unhappy.Unknown.Unseen.Waking.Wild.Wise.Worried.Young`.split(`.`),genitive:`Cold.Day.Death.Doom.Fate.Fire.Fog.Frost.Gates.Heaven.Home.Ice.Justice.Life.Light.Lightning.Love.Nature.Night.Pain.Snow.Springs.Summer.Thunder.Time.Victory.War.Winter`.split(`.`),theGenitive:[`Abyss`,`Blood`,`Dawn`,`Earth`,`East`,`Eclipse`,`Fall`,`Harvest`,`Moon`,`North`,`Peak`,`Rainbow`,`Sea`,`Sky`,`South`,`Stars`,`Storm`,`Sun`,`Tree`,`Underworld`,`West`,`Wild`,`Word`,`World`],color:`Amber.Black.Blue.Bright.Bronze.Brown.Coral.Crimson.Dark.Emerald.Golden.Green.Grey.Indigo.Lavender.Light.Magenta.Maroon.Orange.Pink.Plum.Purple.Red.Ruby.Sapphire.Teal.Turquoise.White.Yellow`.split(`.`)},jr={Folk:{Shamanism:4,Animism:4,Polytheism:4,"Ancestor Worship":2,"Nature Worship":1,Totemism:1},Organized:{Polytheism:7,Monotheism:7,Dualism:3,Syncretism:2,Pantheism:2,"Non-theism":2,Philosophical:1,Ethical:1,Deism:1,Henotheism:1},Cult:{Cult:5,"Dark Cult":5,Sect:1},Heresy:{Heresy:1}},Mr={Shamanism:{"Culture + type":1},Animism:{"Culture + type":1},Polytheism:{"Random + type":4,"Random + ism":1,"Place + ism":1,"Culture + ism":2,"Place + ian + type":6,"Culture + type":4,"Type + of the + meaning":2},"Ancestor Worship":{"Culture + type":1},"Nature Worship":{"Culture + type":1},Totemism:{"Culture + type":1},Monotheism:{"Random + type":2,"Random + ism":1,"Supreme + ism":6,"Faith of + Supreme":6,"Place + ism":1,"Culture + ism":1,"Place + ian + type":4,"Culture + type":3},Dualism:{"Random + type":3,"Random + ism":1,"Place + ism":1,"Culture + ism":2,"Place + ian + type":5,"Culture + type":4,"Type + of the + meaning":3},Syncretism:{"Random + type":3,"Random + ism":2,"Place + ism":1,"Culture + ism":2,"Place + ian + type":5,"Culture + type":4,"Type + of the + meaning":2},Pantheism:{"Random + type":3,"Random + ism":1,"Place + ism":1,"Culture + ism":2,"Place + ian + type":5,"Culture + type":4,"Type + of the + meaning":2},"Non-theism":{"Random + type":3,"Random + ism":2,"Place + ism":1,"Culture + ism":3,"Place + ian + type":4,"Culture + type":5},Philosophical:{"Random + type":3,"Random + ism":2,"Place + ism":1,"Culture + ism":3,"Place + ian + type":4,"Culture + type":5},Ethical:{"Random + type":3,"Random + ism":2,"Place + ism":1,"Culture + ism":3,"Place + ian + type":4,"Culture + type":5},Deism:{"Random + type":2,"Random + ism":1,"Supreme + ism":3,"Faith of + Supreme":3,"Place + ism":1,"Culture + ism":2,"Place + ian + type":5,"Culture + type":4},Henotheism:{"Random + type":2,"Random + ism":1,"Supreme + ism":2,"Faith of + Supreme":2,"Place + ism":1,"Culture + ism":2,"Place + ian + type":6,"Culture + type":4,"Type + of the + meaning":2},Cult:{"Burg + ian + type":2,"Random + ian + type":1,"Type + of the + meaning":2},"Dark Cult":{"Burg + ian + type":2,"Random + ian + type":1,"Type + of the + meaning":3},Sect:{"Burg + ian + type":2,"Random + ian + type":1,"Type + of the + meaning":2},Heresy:{"Burg + ian + type":3,"Random + ism":3,"Random + ian + type":2,"Type + of the + meaning":1}},Nr={Shamanism:{Beliefs:3,Shamanism:1,Druidism:1,Spirits:1},Animism:{Spirits:3,Beliefs:1},Polytheism:{Pantheon:3,Deities:2,Gods:1},"Ancestor Worship":{Beliefs:1,Forefathers:2,Ancestors:2},"Nature Worship":{Beliefs:3,Druids:1,Spirits:1},Totemism:{Beliefs:2,Totems:2,Idols:1},Monotheism:{Religion:2,Church:3,Faith:1,Creed:1,Commandments:1},Dualism:{Religion:3,Faith:1},Syncretism:{Faith:2,Religion:2,Beliefs:1},Pantheism:{Religion:1,Faith:1},"Non-theism":{Beliefs:3,Spirits:1},Philosophical:{Philosophy:3,Doctrine:2,School:1,Way:1},Ethical:{Ethics:2,Doctrine:2,Path:2,Way:2,Precepts:1},Deism:{Faith:2,Religion:1,Church:1,Creed:1},Henotheism:{Faith:2,Religion:1,Gods:1,Pantheon:1},Cult:{Cult:4,Sect:2,Arcanum:1,Order:1,Worship:1,Mysticism:1},"Dark Cult":{Cult:2,Blasphemy:1,Circle:1,Coven:1,Idols:1,Occultism:1},Sect:{Sect:4,Society:1,Brotherhood:1,Circle:1,Way:1},Heresy:{Heresy:3,Sect:2,Apostates:1,Brotherhood:1,Circle:1,Dissent:1,Dissenters:1,Iconoclasm:1,Schism:1,Society:1}},Pr={Folk:()=>0,Organized:()=>Mt(5,3,0,10,1),Cult:()=>Mt(.5,.5,0,5,1),Heresy:()=>Mt(1,.5,0,5,1)};function Fr(e){let t=pack.cultures[e]?.ancestry?.trim();return t?new Set(pack.cultures.filter(e=>e.i&&!e.removed&&e.ancestry?.trim()===t).map(e=>e.i)):new Set([e])}var Ir=new class{regenerate(){this.generate()}generate(){let e=pack.religions?.filter(e=>e.i&&e.lock&&!e.removed)||[],t=this.generateFolkReligions(),n=this.generateOrganizedReligions(options.generation.religions.limit,e),r=this.specifyReligions([...t,...n]),i=this.combineReligions(r,e),a=this.expandReligions(i),o=this.defineOrigins(a,i),s=this.generateHeresies(o,a),c=[...o,...s];for(let e of c)e&&(e.tags=e.tags??[]);this.expandHeresies(c,a,s),pack.religions=c,pack.cells.religion=a,this.checkCenters()}generateFolkReligions(){let e=pack.cultures.filter(e=>e.i&&!e.removed),t=[],n=new Map;for(let r of e){let e=r.ancestry?.trim();if(e){let t=n.get(e);t?t.push(r):n.set(e,[r])}else t.push({type:`Folk`,form:T(jr.Folk),culture:r.i,center:r.center})}for(let e of n.values()){let n=e[0];t.push({type:`Folk`,form:T(jr.Folk),culture:n.i,center:n.center})}return t}generateOrganizedReligions(e,t){let n=pack.cells,r=e-t.filter(({type:e})=>e===`Organized`||e===`Cult`).length;if(r<1)return[];let i=u(),a=l(),o=Math.floor(E(1,4)/10*a.length),s=a.length-o,c=e=>e<s?`Organized`:`Cult`;return a.map((e,t)=>{let r=c(t);return{type:r,form:T(jr[r]),culture:n.culture[e],center:e}});function l(){let a=[],o=Ge();for(let{center:e}of t)o.add(n.p[e]);let s=(options.map.graph.width+options.map.graph.height)/2/e;for(let e of i){let[t,i]=n.p[e];if(o.find(t,i,s)===void 0&&(a.push(e),o.add([t,i]),a.length===r))return a}return h.warn(`Placed only ${a.length} of ${r} religions`),a}function u(){let e=pack.burgs.filter(e=>e.i&&!e.removed);return e.length>=r?e.sort((e,t)=>t.population-e.population).map(e=>e.cell):n.i.filter(e=>n.s[e]>2).sort((e,t)=>n.s[t]-n.s[e])}}specifyReligions(e){let{cells:t,cultures:n}=pack;return e.map(({type:e,form:i,culture:a,center:o})=>{let s=this.getDeityName(a),c=i===`Non-theism`||i===`Animism`?null:s??null,l=t.state[o],[u,d]=this.generateReligionName(e,i,s,o);d===`state`&&!l&&(d=`global`);let f=Pr[e](),p=r(n[a],e);return{name:u,type:e,form:i,culture:a,center:o,deity:c,expansion:d,expansionism:f,color:p}});function r(e,t){return e.i?t===`Folk`?e.color:t===`Heresy`?It(e.color,.35,.2):t===`Cult`?It(e.color,.5,0):It(e.color,.25,.4):zt()}}combineReligions(e,t){let n=[{name:`No religion`,i:0}],{lockedReligionQueue:r,reservedOriginIds:i,highestReservedIndex:a,codes:o,numberLockedFolk:s}=l(),c=Math.max(a+1,e.length+t.length+i.size+1-s);for(let a=1,s=0;a<c;a=n.length)if(a===r[0]?.i){let e=r.shift();n.push(e)}else if(i.has(a))n.push({i:a,type:`Folk`,culture:0,name:`Removed religion`,removed:!0});else if(s<e.length){let r=e[s];if(s++,r.type===`Folk`&&t.some(({type:e,culture:t})=>{if(e!==`Folk`)return!1;if(t===r.culture)return!0;let n=pack.cultures[r.culture]?.ancestry?.trim(),i=pack.cultures[t]?.ancestry?.trim();return!!(n&&i&&n===i)}))continue;let i=u(r),c=At(i,o);o.push(c),n.push({...r,i:a,name:i,code:c})}else n.push({i:a,type:`Folk`,culture:0,name:`Removed religion`,removed:!0});return n;function l(){let e=t.map(e=>({...e})).sort((e,t)=>e.i-t.i),n=new Set(t.map(e=>e.i)),r=new Set(t.flatMap(e=>e.origins??[]).filter(e=>e>0&&!n.has(e)));return{lockedReligionQueue:e,reservedOriginIds:r,highestReservedIndex:Math.max(...n,...r,0),codes:t.length>0?t.map(e=>e.code):[],numberLockedFolk:t.filter(({type:e})=>e===`Folk`).length}}function u({name:n,type:r,culture:i}){if(r!==`Folk`)return n;let a=Fr(i);return(e.some(({type:e,culture:t,expansion:n})=>a.has(t)&&e===`Organized`&&n===`culture`)||t.some(({type:e,culture:t,expansion:n})=>a.has(t)&&e===`Organized`&&n===`culture`))&&n.slice(0,3)!==`Old`?`Old ${n}`:n}}defineOrigins(e,t){let n={Organized:{clusterSize:100,maxReligions:2},Cult:{clusterSize:50,maxReligions:3}},r=[...t];for(let i of t){let{i:t,type:a,culture:o,expansion:s,center:c}=i;if(t===0){r[t]={...i,origins:null};continue}if(i.lock||a===`Heresy`)continue;if(a===`Folk`){r[t]={...i,origins:[0]};continue}let l=r.find(({culture:e,type:t})=>t===`Folk`&&e===o);if(l&&o&&s===`culture`&&Ct(2)(c)){r[t]={...i,origins:[l.i]};continue}let{clusterSize:u,maxReligions:d}=n[a],f=l?.i||0,p=this.getReligionsInRadius(pack.cells.c,c,e,t,u,d,f,r);r[t]={...i,origins:p}}return r}generateHeresies(e,t){let n=e.filter(e=>e.type===`Organized`&&!e.lock&&!e.removed&&(e.expansionism??0)>=3);if(!n.length)return[];let r=new Set(n.map(e=>e.i)),i=new Map;for(let e of pack.cells.i){let n=t[e];if(!r.has(n)||!pack.cells.c[e].some(e=>t[e]!==n))continue;let a=i.get(n)??[];a.push(e),i.set(n,a)}let a=new Set(e.filter(e=>!e.removed).map(e=>e.center)),o=e.map(e=>e.code),s=[];for(let t of n){let n=(i.get(t.i)??[]).filter(e=>!a.has(e)),r=Mt(0,1,0,3);for(let i=0;i<r&&n.length;i++){let r=E(0,n.length-1),i=n.splice(r,1)[0],c=this.createHeresy(t,i,e.length+s.length,o);a.add(i),o.push(c.code),s.push(c)}}return s}createHeresy(e,t,n,r){let[i,a]=this.generateReligionName(`Heresy`,`Heresy`,e.deity??``,t);return{i:n,name:i,color:It(e.color,.4,.2),culture:pack.cells.culture[t],type:`Heresy`,form:e.form,deity:e.deity,expansion:a,expansionism:Pr.Heresy(),center:t,cells:0,area:0,rural:0,urban:0,origins:[e.i],code:At(i,r),tags:[]}}getReligionsInRadius(e,t,n,r,i,a,o,s){let c=new Set,l=[t],u={};for(let t=0;l.length&&t<i;t++){let t=l.shift();u[t]=!0;for(let i of e[t]){if(u[i])continue;u[i]=!0;let e=n[i];if(e&&e<r&&!this.wouldCreateOriginCycle(r,e,s)&&c.add(e),c.size>=a)return[...c];l.push(i)}}return c.size?[...c]:this.wouldCreateOriginCycle(r,o,s)?[0]:[o]}wouldCreateOriginCycle(e,t,n){let r=[t],i=new Set;for(;r.length;){let t=r.shift();if(t===e)return!0;t&&!i.has(t)&&(i.add(t),r.push(...(n[t]?.origins??[]).filter(e=>e!==null)))}return!1}expandReligions(e){let{cells:t}=pack,n=this.spreadFolkReligions(e),r=new se,i=[],a=t.i.length/20*options.generation.cultures.growthRate;e.filter(e=>e.i&&!e.lock&&e.type!==`Folk`&&e.type!==`Heresy`&&!e.removed).forEach(e=>{n[e.center]=e.i,r.push({e:e.center,p:0,r:e.i,s:t.state[e.center]},0),i[e.center]=1});let o=new Map(e.map(e=>[e.i,e]));for(;r.length;){let{e,p:s,r:c,s:l}=r.pop(),{culture:u,expansion:d,expansionism:f}=o.get(c);t.c[e].forEach(p=>{if(d===`culture`&&u!==t.culture[p]||d===`state`&&l!==t.state[p]||o.get(n[p])?.lock)return;let m=u===t.culture[p]?0:10,h=l===t.state[p]?0:10,ee=this.getPassageCost(e,p),te=m+h+ee,ne=s+10+te/f;ne>a||(!i[p]||ne<i[p])&&(t.culture[p]&&(n[p]=c),i[p]=ne,r.push({e:p,p:ne,r:c,s:l},ne))})}return n}expandHeresies(e,t,n){if(!n.length)return;let{cells:r}=pack,i=new se,a=[],o=r.i.length/20*options.generation.cultures.growthRate,s=new Map(e.map(e=>[e.i,e]));for(let e of n){let n=e.origins?.[0];n&&s.get(n)?.type===`Organized`&&(s.get(t[e.center])?.lock||(t[e.center]=e.i,i.push({e:e.center,p:0,r:e.i,b:n},0),a[e.center]=1))}for(;i.length;){let{e,p:n,r:c,b:l}=i.pop(),u=s.get(c);for(let d of r.c[e]){if(s.get(t[d])?.lock)continue;let f=t[d]===l?0:2e3,p=this.getPassageCost(e,d),m=n+10+(f+p)/Math.max(u.expansionism,.1);m>o||(!a[d]||m<a[d])&&(r.culture[d]&&(t[d]=c),a[d]=m,i.push({e:d,p:m,r:c,b:l},m))}}}normalizeHeresiesForExpansion(e,t){let n=new Map(e.map(e=>[e.i,e])),r=e.filter(e=>e.type===`Organized`&&!e.lock&&!e.removed);return e.filter(e=>e.type===`Heresy`&&!e.lock&&!e.removed).flatMap(i=>{let a=n.get(t[i.center]),o=[...(i.origins??[]).map(e=>n.get(e)),a,...r],s=new Set,c=o.find(t=>!t||s.has(t.i)?!1:(s.add(t.i),t.type===`Organized`&&!t.lock&&!t.removed&&!this.wouldCreateOriginCycle(i.i,t.i,e)));if(!c){i.removed=!0,i.origins=[0],i.cells=0,i.area=0,i.rural=0,i.urban=0;for(let t of e){if(t.lock||!t.origins?.includes(i.i))continue;let e=t.origins.filter(e=>e!==i.i);t.origins=e.length?e:[0]}return[]}return i.origins=[c.i],i.form=c.form,i.deity=c.deity,[i]})}getPassageCost(e,t){let n=_.getRoute(e,t);if(qe(e,pack))return n?50:500;let r=pack.biomes[pack.cells.biome[t]].cost;return n?n.group===`roads`?1:r/3:r}spreadFolkReligions(e){let t=pack.cells,n=t.religion&&!0,r=new Uint16Array(t.i.length),i=e.filter(e=>e.type===`Folk`&&!e.removed),a=new Map;for(let e of i)a.set(e.culture,e.i);for(let e of i){let t=pack.cultures[e.culture]?.ancestry?.trim();if(t)for(let n of pack.cultures)n.i&&!n.removed&&n.ancestry?.trim()===t&&(a.has(n.i)||a.set(n.i,e.i))}for(let i of t.i){let o=n&&t.religion[i]||0;if(o&&e[o]?.lock&&!e[o]?.removed){r[i]=o;continue}let s=t.culture[i];r[i]=a.get(s)||0}return r}checkCenters(){let e=pack.cells;pack.religions.forEach(t=>{if(!t.i||e.religion[t.center]===t.i)return;let n=e.i.find(n=>e.religion[n]===t.i),r=pack.cultures[t.culture]?.center;n?t.center=n:t.type===`Folk`&&r&&(t.center=r)})}recalculate(){let e=this.expandReligions(pack.religions),t=this.normalizeHeresiesForExpansion(pack.religions,e);this.expandHeresies(pack.religions,e,t),pack.cells.religion=e,this.checkCenters()}rename(e,t){let n=pack.religions[e];if(!n||n.removed)throw Error(`Religion ${e} does not exist`);n.name=y(t),n.code=At(n.name,pack.religions.flatMap(e=>e!==n&&e.code?[e.code]:[]))}recolor(e,t){this.living(e).color=Bt(t)}setDeity(e,t){this.living(e).deity=String(t??``).trim()||null}setType(e,t){this.living(e).type=Ce(t,Dr,`The type`)}setForm(e,t){this.living(e).form=y(t)}setExpansion(e,t){this.living(e).expansion=Ce(t,Or,`The expansion`)}setExpansionism(e,t){if(typeof t!=`number`||!(t>=0&&t<=99))throw Error(`The expansionism must be a number from 0 to 99`);this.living(e).expansionism=t}remove(e){let t=this.living(e);if(!e)throw Error(`No religion cannot be removed`);pack.cells.religion.forEach((t,n)=>{t===e&&(pack.cells.religion[n]=0)}),t.removed=!0;for(let t of pack.religions)t.i&&!t.removed&&t.origins&&(t.origins=t.origins.filter(t=>t!==e),t.origins.length||(t.origins=[0]))}setPopulation(e,t,n){this.living(e);let{cells:r}=pack;he.setArea(he.landCells(t=>r.religion[t]===e),he.burgIds(t=>r.religion[t.cell]===e),t,n)}setLocked(e,t){let n=this.living(e);t?n.lock=!0:delete n.lock}setOrigins(e,t){this.living(e).origins=Me(pack.religions,e,t)}setCode(e,t){this.living(e).code=Le(t)}moveCenter(e,t,n){let r=this.living(e);if(!e)throw Error(`Lands without religion have no center`);let i=S.requireCell(t,n);if(pack.cells.h[i]<20)throw Error(`A religion center cannot be placed in the water`);let a=pack.religions.find(e=>e.i&&!e.removed&&e!==r&&e.center===i);if(a)throw Error(`Cell ${i} is already the center of religion ${a.i}`);r.center=i}setCells(e,t){this.living(e);let{cells:n}=pack;if(!Array.isArray(t)||!t.length)throw Error(`Name at least one cell`);for(let e of t){if(!Number.isInteger(e)||e<0||e>=n.i.length)throw Error(`Cell ${e} does not exist`);if(n.h[e]<20)throw Error(`Cell ${e} is water; religions hold land only`)}for(let r of t)n.religion[r]=e}living(e){let t=pack.religions[e];if(!t||t.removed)throw Error(`Religion ${e} does not exist`);return t}add(e,t){let{cells:n,cultures:r,religions:i}=pack,a=S.requireCell(e,t);if(n.h[a]<20)throw Error(`A religion center cannot be placed in the water`);if(i.some(e=>e.i&&!e.removed&&e.center===a))throw Error(`Cell ${a} is already a religion center`);let o=n.religion[a],s=i.length,c=n.culture[a],l=Fr(c),u=c!==0&&!i.some(({type:e,culture:t,removed:n})=>e===`Folk`&&l.has(t)&&!n),d=i[o],f=u?`Folk`:i[o].type===`Organized`?T({Organized:4,Cult:1,Heresy:2}):T({Organized:5,Cult:2}),p=i.map(e=>e.code);if(f===`Heresy`)return i.push(this.createHeresy(d,a,s,p)),n.religion[a]=s,s;let m=u?r[c].color:It(d.color,.3,0),h=T(jr[f]),ee=h===`Non-theism`||h===`Animism`?null:this.getDeityName(c)??null,[te,ne]=this.generateReligionName(f,h,ee??``,a),re=At(te,p),ie=this.getReligionsInRadius(n.c,a,n.religion,s,25,3,0,i),ae=f===`Folk`?[0]:ie;return i.push({i:s,name:te,color:m,culture:c,type:f,form:h,deity:ee,expansion:ne,expansionism:Pr[f](),center:a,cells:0,area:0,rural:0,urban:0,origins:ae,code:re,tags:[]}),n.religion[a]=s,s}getDeityName(e){if(e===void 0){h.error(`Please define a culture`);return}let t=this.generateMeaning();return`${A.getCulture(e)}, The ${t}`}generateReligionName(e,t,n,r){let{cells:i,cultures:a,burgs:o,states:s}=pack,c=()=>A.getCulture(i.culture[r]),l=T(Nr[t]),u=n.split(/[ ,]+/)[0],d=a[i.culture[r]],f=d?.ancestry?.trim(),p=e===`Folk`&&f||d?.name,m=e=>{let t=i.burg[r],n=i.state[r],a=t?o[t].name:s[n].name,c=Tt(a.split(/[ ,]+/)[0]);return e?k(c):c},h=T(Mr[t]||Mr[e]);return e===`Folk`&&f?h===`Culture + ism`?[`${Tt(f)}ism`,`culture`]:[`${f} ${l}`,`culture`]:h===`Random + type`?[`${c()} ${l}`,`global`]:h===`Random + ism`?[`${Tt(c())}ism`,`global`]:h===`Supreme + ism`&&n?[`${Tt(u)}ism`,`global`]:h===`Faith of + Supreme`&&n?[`${D([`Faith`,`Way`,`Path`,`Word`,`Witnesses`])} of ${u}`,`global`]:h===`Place + ism`?[`${m()}ism`,`state`]:h===`Culture + ism`?[`${Tt(p)}ism`,`culture`]:h===`Place + ian + type`?[`${m(!0)} ${l}`,`state`]:h===`Culture + type`?[`${p} ${l}`,`culture`]:h===`Burg + ian + type`?[`${m(!0)} ${l}`,`global`]:h===`Random + ian + type`?[`${k(c())} ${l}`,`global`]:h===`Type + of the + meaning`?[`${l} of the ${this.generateMeaning()}`,`global`]:[`${Tt(c())}ism`,`global`]}generateMeaning(){let e=D(Ar);return e===`Number`?D(U.number):e===`Being`?D(U.being):e===`Adjective`?D(U.adjective):e===`Color + Animal`?`${D(U.color)} ${D(U.animal)}`:e===`Adjective + Animal`?`${D(U.adjective)} ${D(U.animal)}`:e===`Adjective + Being`?`${D(U.adjective)} ${D(U.being)}`:e===`Adjective + Genitive`?`${D(U.adjective)} ${D(U.genitive)}`:e===`Color + Being`?`${D(U.color)} ${D(U.being)}`:e===`Color + Genitive`?`${D(U.color)} ${D(U.genitive)}`:e===`Being + of + Genitive`?`${D(U.being)} of ${D(U.genitive)}`:e===`Being + of the + Genitive`?`${D(U.being)} of the ${D(U.theGenitive)}`:e===`Animal + of + Genitive`?`${D(U.animal)} of ${D(U.genitive)}`:e===`Adjective + Being + of + Genitive`?`${D(U.adjective)} ${D(U.being)} of ${D(U.genitive)}`:e===`Adjective + Animal + of + Genitive`?`${D(U.adjective)} ${D(U.animal)} of ${D(U.genitive)}`:(h.error(`Unknown generation approach`),D(U.being))}},Lr=[`bubble`,`pin`,`square`,`squarish`,`diamond`,`hex`,`hexy`,`shieldy`,`shield`,`pentagon`,`heptagon`,`circle`,`no`],Rr={1:[`Camels`,`Antelopes`,`Jackals`,`Hyenas`,`Scorpions`,`Locusts`],2:[`Camels`,`Goats`,`Wolves`,`Foxes`,`Eagles`,`Falcons`],3:[`Antelopes`,`Buffalo`,`Elephants`,`Lions`,`Hyenas`,`Cranes`,`Zebras`],4:[`Bisons`,`Horses`,`Deer`,`Hares`,`Geese`,`Larks`,`Wolves`],5:[`Apes`,`Elephants`,`Leopards`,`Tigers`,`Parrots`,`Mantises`],6:[`Deer`,`Boars`,`Badgers`,`Foxes`,`Crows`,`Rooks`,`Bears`,`Wolves`],7:[`Apes`,`Jaguars`,`Panthers`,`Snakes`,`Spiders`,`Parrots`],8:[`Elk`,`Deer`,`Bears`,`Beavers`,`Owls`,`Ravens`],9:[`Elk`,`Moose`,`Wolves`,`Wolverines`,`Martens`,`Bears`,`Ravens`],10:[`Reindeer`,`Musk oxen`,`Wolves`,`Foxes`,`Geese`,`Hares`,`Owls`],12:[`Herons`,`Cranes`,`Ibises`,`Geese`,`Crocodiles`,`Frogs`]},zr={"Healing Spring":5,"Purifying Well":2,"Enchanted Reservoir":1,"Creek of Luck":1,"Fountain of Youth":1,"Wisdom Spring":1,"Spring of Life":1,"Spring of Youth":1,"Healing Stream":1},Br={stone:10,wooden:1,lengthy:2,formidable:2,rickety:1,beaten:1,weathered:1},Vr=[`its collapse during the flood`,`being rumoured to attract trolls`,`the drying up of local trade`,`banditry infested the area`,`the old waypoints crumbled`],Hr=[`Dark`,`Light`,`Bright`,`Golden`,`White`,`Black`,`Red`,`Pink`,`Purple`,`Blue`,`Green`,`Yellow`,`Amber`,`Orange`,`Brown`,`Grey`],Ur=`Antelope.Ape.Badger.Bear.Beaver.Bison.Boar.Buffalo.Cat.Crane.Crocodile.Crow.Deer.Dog.Eagle.Elk.Fox.Goat.Goose.Hare.Hawk.Heron.Horse.Hyena.Ibis.Jackal.Jaguar.Lark.Leopard.Lion.Mantis.Marten.Moose.Mule.Narwhal.Owl.Panther.Rat.Raven.Rook.Scorpion.Shark.Sheep.Snake.Spider.Swan.Tiger.Turtle.Wolf.Wolverine.Camel.Falcon.Hound.Ox`.split(`.`),Wr=`New.Good.High.Old.Great.Big.Major.Happy.Main.Huge.Far.Beautiful.Fair.Prime.Ancient.Golden.Proud.Lucky.Fat.Honest.Giant.Distant.Friendly.Loud.Hungry.Magical.Superior.Peaceful.Frozen.Divine.Favorable.Brave.Sunny.Flying`.split(`.`),Gr=[`Boiled`,`Grilled`,`Roasted`,`Spit-roasted`,`Stewed`,`Stuffed`,`Jugged`,`Mashed`,`Baked`,`Braised`,`Poached`,`Marinated`,`Pickled`,`Smoked`,`Dried`,`Dry-aged`,`Corned`,`Fried`,`Pan-fried`,`Deep-fried`,`Dressed`,`Steamed`,`Cured`,`Syrupped`,`Flame-Broiled`],Kr={Cattle:[`beef`,`veal`],Sheep:[`lamb`,`mutton`],Game:[`hare`,`rabbit`,`hart`,`deer`,`antlers`,`bear`,`buffalo`,`badger`,`beaver`,`boar`,`pheasant`],Fish:[`carp`,`bass`,`pike`,`catfish`,`sturgeon`,`escallop`,`eel`],Whales:[`whale`,`seal`],Camels:[`camel`],Grain:[`bread`,`pie`,`cake`,`pottage`,`pudding`,`pasta`],Olives:[`olives`],Dates:[`dates`],Cheese:[`cheese`]},qr=[`pork`,`bacon`,`chicken`,`goose`,`duck`,`pigeon`,`chevon`,`eggs`,`onions`,`carrot`,`potato`,`beet`,`garlic`,`cabbage`,`spinach`,`peas`,`beans`,`pumpkin`,`apples`,`pears`,`rat tails`,`pig ears`],Jr=[`rice`,`chickpea`,`eggplant`,`zucchini`,`pepper`,`tomatoes`,`melon`,`oranges`,`mango`],Yr=[`hot`,`cold`,`fire`,`ice`,`smoky`,`misty`,`shiny`,`sweet`,`bitter`,`salty`,`sour`,`sparkling`,`smelly`],Xr={Wine:[`wine`,`brandy`],Beer:[`beer`,`ale`],Liquor:[`gin`,`whisky`,`rum`,`vodka`,`tequila`,`absinthe`,`liquor`,`spirits`],Grain:[`kvass`],Honey:[`mead`,`nectar`],Sugarcane:[`rum`],Tea:[`tea`],Cattle:[`milk`],Horses:[`kumis`]},Zr=[`water`,`cider`,`juice`,`sap`],Qr=[`A gorgeous waterfall flows here.`,`The rapids of an exceptionally beautiful waterfall.`,`An impressive waterfall has cut through the land.`,`The cascades of a stunning waterfall.`,`A river drops down from a great height forming a wondrous waterfall.`,`A breathtaking waterfall cuts through the landscape.`],$r=[`Locals`,`Elders`,`Inscriptions`,`Tipplers`,`Legends`,`Whispers`,`Rumors`,`Journeying folk`,`Tales`],ei=[`great`,`big`,`huge`,`prime`,`golden`,`proud`,`lucky`,`fat`,`giant`,`hungry`,`magical`,`superior`,`terrifying`,`horrifying`,`feared`],ti=[`Ogre`,`Troll`,`Cyclops`,`Giant`,`Monster`,`Beast`,`Dragon`,`Undead`,`Ghoul`,`Vampire`,`Hag`,`Banshee`,`Bearded Devil`,`Roc`,`Hydra`,`Warg`],ni=[`steals cattle at night`,`prefers eating children`,`doesn't mind human flesh`,`keeps the region at bay`,`eats kids whole`,`abducts young women`,`terrorizes the region`,`harasses travelers in the area`,`snatches people from homes`,`attacks anyone who dares to approach its lair`,`attacks unsuspecting victims`],ri=`Apes.Badgers.Bears.Beavers.Bisons.Boars.Cats.Crows.Dogs.Foxes.Hares.Hawks.Hyenas.Jackals.Jaguars.Leopards.Lions.Owls.Panthers.Rats.Ravens.Rooks.Scorpions.Sharks.Snakes.Spiders.Tigers.Wolfs.Wolverines.Falcons`.split(`.`),ii={brigands:4,bandits:3,robbers:1,highwaymen:1},ai=[`Statue`,`Obelisk`,`Monument`,`Column`,`Monolith`,`Pillar`,`Megalith`,`Stele`,`Runestone`,`Sculpture`,`Effigy`,`Idol`],oi={cypriot:`𐠁𐠂𐠃𐠄𐠅𐠈𐠊𐠋𐠌𐠍𐠎𐠏𐠐𐠑𐠒𐠓𐠔𐠕𐠖𐠗𐠘𐠙𐠚𐠛𐠜𐠝𐠞𐠟𐠠𐠡𐠢𐠣𐠤𐠥𐠦𐠧𐠨𐠩𐠪𐠫𐠬𐠭𐠮𐠯𐠰𐠱𐠲𐠳𐠴𐠵𐠷𐠸𐠼𐠿      `,geez:`ሀለሐመሠረሰቀበተኀነአከወዐዘየደገጠጰጸፀፈፐ   `,coptic:`ⲲⲴⲶⲸⲺⲼⲾⳀⳁⳂⳃⳄⳆⳈⳊⳌⳎⳐⳒⳔⳖⳘⳚⳜⳞⳠⳢⳤ⳥⳧⳩⳪ⳫⳬⳭⳲ⳹⳾   `,tibetan:`ༀ༁༂༃༄༅༆༇༈༉༊་༌༐༑༒༓༔༕༖༗༘༙༚༛༜༠༡༢༣༤༥༦༧༨༩༪༫༬༭༮༯༰༱༲༳༴༵༶༷༸༹༺༻༼༽༾༿`,mongolian:`᠀᠐᠑᠒ᠠᠡᠦᠧᠨᠩᠪᠭᠮᠯᠰᠱᠲᠳᠵᠻᠼᠽᠾᠿᡀᡁᡆᡍᡎᡏᡐᡑᡒᡓᡔᡕᡖᡗᡙᡜᡝᡞᡟᡠᡡᡭᡮᡯᡰᡱᡲᡳᡴᢀᢁᢂᢋᢏᢐᢑᢒᢓᢛᢜᢞᢟᢠᢡᢢᢤᢥᢦ`},si=[`City`,`Town`,`Settlement`,`Pyramid`,`Fort`,`Stronghold`,`Temple`,`Sacred site`,`Mausoleum`,`Outpost`,`Fortification`,`Fortress`,`Castle`],ci={Library:3,Archive:1,Collection:1},li=[`Fantastical`,`Wondrous`,`Incomprehensible`,`Magical`,`Extraordinary`,`Unmissable`,`World-famous`,`Breathtaking`],ui=[`Joust`,`Competition`,`Melee`,`Tournament`,`Contest`],di=[`cunning`,`might`,`speed`,`the greats`,`acumen`,`brutality`],fi=[`gala`,`dance`,`performance`,`ball`,`soiree`,`jamboree`,`exhibition`,`carnival`,`festival`,`jubilee`,`celebration`,`gathering`,`fete`],pi=[`great and the good`,`nobility`,`local elders`,`foreign dignitaries`,`spiritual leaders`,`suspected revolutionaries`],mi=[`Entrancing`,`Diaphanous`,`Illusory`,`Distant`,`Peculiar`],hi={Cave:10,Cavern:8,Chasm:6,Ravine:6,Fracture:5,Grotto:4,Pit:4,Sinkhole:2,Hole:2},gi={"a good spot to hid treasure":5,"the home of strange monsters":5,"totally empty":4,"endlessly deep and unexplored":4,"completely flooded":2,"slowly filling with lava":1},_i=[`Demonic`,`Interdimensional`,`Abyssal`,`Cosmic`,`Cataclysmic`,`Subterranean`,`Ancient`],vi=[`all known nearby beings to flee in terror`,`cracks in reality itself to form`,`swarms of foes to spill forth`,`nearby plants to wither and decay`,`an emmissary to step through with an all-powerful relic`],yi={Necropolis:5,Crypt:2,Tomb:2,Graveyard:1,Cemetery:2,Mausoleum:1,Sepulchre:1},bi=[`A foreboding necropolis shrouded in perpetual darkness, where eerie whispers echo through the winding corridors and spectral guardians stand watch over the tombs of long-forgotten souls.`,`A towering necropolis adorned with macabre sculptures and guarded by formidable undead sentinels. Its ancient halls house the remains of fallen heroes, entombed alongside their cherished relics.`,`This ethereal necropolis seems suspended between the realms of the living and the dead. Wisps of mist dance around the tombstones, while haunting melodies linger in the air, commemorating the departed.`,`Rising from the desolate landscape, this sinister necropolis is a testament to necromantic power. Its skeletal spires cast ominous shadows, concealing forbidden knowledge and arcane secrets.`,`An eerie necropolis where nature intertwines with death. Overgrown tombstones are entwined by thorny vines, and mournful spirits wander among the fading petals of once-vibrant flowers.`,`A labyrinthine necropolis where each step echoes with haunting murmurs. The walls are adorned with ancient runes, and restless spirits guide or hinder those who dare to delve into its depths.`,`This cursed necropolis is veiled in perpetual twilight, perpetuating a sense of impending doom. Dark enchantments shroud the tombs, and the moans of anguished souls resound through its crumbling halls.`,`A sprawling necropolis built within a labyrinthine network of catacombs. Its halls are lined with countless alcoves, each housing the remains of the departed, while the distant sound of rattling bones fills the air.`,`A desolate necropolis where an eerie stillness reigns. Time seems frozen amidst the decaying mausoleums, and the silence is broken only by the whispers of the wind and the rustle of tattered banners.`,`A foreboding necropolis perched atop a jagged cliff, overlooking a desolate wasteland. Its towering walls harbor restless spirits, and the imposing gates bear the marks of countless battles and ancient curses.`],xi=[{subject:`Bandits`,verb:`have set an ambush`},{subject:`Wild beasts`,verb:`have been sighted`},{subject:`A lone traveler`,verb:`was seen wandering`},{subject:`Cultists`,verb:`gather in secret`},{subject:`A pilgrim`,verb:`walks the road`},{subject:`Refugees`,verb:`have made camp`},{subject:`Smugglers`,verb:`move under cover of night`},{subject:`A hermit`,verb:`dwells alone`},{subject:`Mercenaries`,verb:`ride through`},{subject:`Poachers`,verb:`have been active`}],Si=(e=100,t=1e3)=>new Date(E(e,t),E(11),E(1,28)).toLocaleDateString(`en`,{year:`numeric`,month:`long`,day:`numeric`});function Ci(e){return e?s(e.replaceAll(`-`,` `)):`Marker`}var wi=(e,t)=>n=>{if(typeof n!=`number`||!(n>=e&&n<=t))throw Error(`Expected a number from ${e} to ${t}`);return n},Ti={size:wi(1,500),px:wi(1,50),dx:wi(0,100),dy:wi(0,100),pin:e=>Ce(e,Lr,`The pin`),fill:Bt,stroke:Bt,iconFill:Bt,iconStroke:Bt},Ei=new class{configuration;occupied=[];get config(){return this.configuration??=this.getDefaultConfig(),this.configuration}set config(e){this.configuration=e}getConfig(){return this.config}setConfig(e){this.config=e}generate(){this.resetConfig(),pack.markers=[],this.generateTypes()}regenerate(){pack.markers=pack.markers.filter(({lock:e,cell:t})=>e?(this.occupied[t]=!0,!0):!1),this.generateTypes()}add(e){let t=this.config.find(t=>t.type===e.type);if(t){let{icon:n,type:r,dx:i,dy:a,px:o,size:s,pin:c,fill:l,stroke:u}=t;return e=this.addMarker({icon:n,type:r,dx:i,dy:a,px:o,size:s,pin:c,fill:l,stroke:u},e),t.add(e,e.cell),e}let n=rt(pack.markers)?.i+1||0,r={...e,i:n,name:e.name||Ci(e.type),tags:e.tags??[]};return pack.markers.push(r),this.occupied[e.cell]=!0,r}rename(e,t){let n=pack.markers.find(t=>t.i===e);if(!n)throw Error(`Marker ${e} does not exist`);n.name=y(t)}setIcon(e,t){this.living(e).icon=Oe.reference(t)}setType(e,t){this.living(e).type=y(t)}setHidden(e,t){let n=this.living(e);t?n.hidden=!0:delete n.hidden}move(e,t,n){let i=this.living(e),a=S.requireCell(t,n);Object.assign(i,{x:r(t,1),y:r(n,1),cell:a})}setPinned(e,t){let n=this.living(e);t?n.pinned=!0:delete n.pinned}setLocked(e,t){let n=this.living(e);t?n.lock=!0:delete n.lock}setAppearance(e,t){let n=this.living(e);if(typeof t!=`object`||!t)throw Error(`The appearance must be an object`);let r={};for(let[e,n]of Object.entries(t)){if(!(e in Ti))throw Error(`Unknown marker appearance ${e}; known: ${Object.keys(Ti).join(`, `)}`);r[e]=n===null?null:Ti[e](n)}for(let[e,t]of Object.entries(r))t===null?delete n[e]:Object.assign(n,{[e]:t})}living(e){let t=pack.markers.find(t=>t.i===e);if(!t)throw Error(`Marker ${e} does not exist`);return t}place(e,t,n,i={}){if(typeof i!=`object`||!i||Array.isArray(i))throw Error(`The marker details must be an object: { name, note, icon }`);let a=Object.keys(i).find(e=>![`name`,`note`,`icon`].includes(e));if(a)throw Error(`Unknown marker detail ${a}; known: name, note, icon`);let{name:o,note:s,icon:c}=i,l=S.requireCell(e,t),u={x:r(e,2),y:r(t,2),cell:l,type:y(n)},d=this.config.some(e=>e.type===u.type);if(!d&&!s)throw Error(`Marker type ${u.type} generates no legend; give the marker a note`);o!==void 0&&(u.name=y(o)),c===void 0?d||(u.icon=Oe.glyph(`❓`)):u.icon=Oe.reference(c);let f=this.add(u);return u.name&&(f.name=u.name),s&&mn.write(`marker:${f.i}`,s),f.i}remove(e){this.living(e),pack.markers=pack.markers.filter(t=>t.i!==e)}listParty({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.burg[t])}addParty(e,t){pack.markers.some(t=>t.type===`party`&&t.i!==e.i&&t.note)||(e.name=`The Party`,e.note=`Current location of the adventuring party.`)}getDefaultConfig(){let e=options.map.cultures.set.includes(`Fantasy`);return[{type:`volcanoes`,icon:`🌋`,dx:52,px:13,min:10,each:500,multiplier:1,list:this.listVolcanoes.bind(this),add:this.addVolcano.bind(this)},{type:`hot-springs`,icon:`♨️`,dy:52,min:30,each:1200,multiplier:1,list:this.listHotSprings.bind(this),add:this.addHotSpring.bind(this)},{type:`water-sources`,icon:`💧`,min:1,each:1e3,multiplier:1,list:this.listWaterSources.bind(this),add:this.addWaterSource.bind(this)},{type:`mines`,icon:`⛏️`,dx:48,px:13,min:1,each:15,multiplier:1,list:this.listMines.bind(this),add:this.addMine.bind(this)},{type:`bridges`,icon:`🌉`,px:14,min:1,each:5,multiplier:1,list:this.listBridges.bind(this),add:this.addBridge.bind(this)},{type:`inns`,icon:`🍻`,px:14,min:1,each:10,multiplier:1,list:this.listInns.bind(this),add:this.addInn.bind(this)},{type:`lighthouses`,icon:`🚨`,px:14,min:1,each:2,multiplier:1,list:this.listLighthouses.bind(this),add:this.addLighthouse.bind(this)},{type:`waterfalls`,icon:`⟱`,dy:54,px:16,min:1,each:5,multiplier:1,list:this.listWaterfalls.bind(this),add:this.addWaterfall.bind(this)},{type:`battlefields`,icon:`⚔️`,dy:52,min:50,each:700,multiplier:1,list:this.listBattlefields.bind(this),add:this.addBattlefield.bind(this)},{type:`dungeons`,icon:`🗝️`,dy:51,px:13,min:30,each:200,multiplier:1,list:this.listDungeons.bind(this),add:this.addDungeon.bind(this)},{type:`lake-monsters`,icon:`🐉`,dy:48,min:2,each:10,multiplier:1,list:this.listLakeMonsters.bind(this),add:this.addLakeMonster.bind(this)},{type:`sea-monsters`,icon:`🦑`,min:50,each:700,multiplier:1,list:this.listSeaMonsters.bind(this),add:this.addSeaMonster.bind(this)},{type:`hill-monsters`,icon:`👹`,dy:54,px:13,min:30,each:600,multiplier:1,list:this.listHillMonsters.bind(this),add:this.addHillMonster.bind(this)},{type:`sacred-mountains`,icon:`🗻`,dy:48,min:1,each:5,multiplier:1,list:this.listSacredMountains.bind(this),add:this.addSacredMountain.bind(this)},{type:`sacred-forests`,icon:`🌳`,min:30,each:1e3,multiplier:1,list:this.listSacredForests.bind(this),add:this.addSacredForest.bind(this)},{type:`sacred-pineries`,icon:`🌲`,px:13,min:30,each:800,multiplier:1,list:this.listSacredPineries.bind(this),add:this.addSacredPinery.bind(this)},{type:`sacred-palm-groves`,icon:`🌴`,px:13,min:1,each:100,multiplier:1,list:this.listSacredPalmGroves.bind(this),add:this.addSacredPalmGrove.bind(this)},{type:`brigands`,icon:`💰`,px:13,min:50,each:100,multiplier:1,list:this.listBrigands.bind(this),add:this.addBrigands.bind(this)},{type:`pirates`,icon:`🏴‍☠️`,dx:51,min:40,each:300,multiplier:1,list:this.listPirates.bind(this),add:this.addPirates.bind(this)},{type:`statues`,icon:`🗿`,min:80,each:1200,multiplier:1,list:this.listStatues.bind(this),add:this.addStatue.bind(this)},{type:`ruins`,icon:`🏺`,min:80,each:1200,multiplier:1,list:this.listRuins.bind(this),add:this.addRuins.bind(this)},{type:`libraries`,icon:`📚`,min:10,each:1200,multiplier:1,list:this.listLibraries.bind(this),add:this.addLibrary.bind(this)},{type:`circuses`,icon:`🎪`,min:80,each:1e3,multiplier:1,list:this.listCircuses.bind(this),add:this.addCircus.bind(this)},{type:`jousts`,icon:`🤺`,dx:48,min:5,each:500,multiplier:1,list:this.listJousts.bind(this),add:this.addJoust.bind(this)},{type:`fairs`,icon:`🎠`,min:50,each:1e3,multiplier:1,list:this.listFairs.bind(this),add:this.addFair.bind(this)},{type:`canoes`,icon:`🛶`,min:500,each:2e3,multiplier:1,list:this.listCanoes.bind(this),add:this.addCanoe.bind(this)},{type:`migration`,icon:`🐗`,min:20,each:1e3,multiplier:1,list:this.listMigrations.bind(this),add:this.addMigration.bind(this)},{type:`dances`,icon:`💃🏽`,min:50,each:1e3,multiplier:1,list:this.listDances.bind(this),add:this.addDances.bind(this)},{type:`mirage`,icon:`💦`,min:10,each:400,multiplier:1,list:this.listMirage.bind(this),add:this.addMirage.bind(this)},{type:`caves`,icon:`🦇`,min:60,each:1e3,multiplier:1,list:this.listCaves.bind(this),add:this.addCave.bind(this)},{type:`portals`,icon:`🌀`,px:14,min:16,each:8,multiplier:+e,list:this.listPortals.bind(this),add:this.addPortal.bind(this)},{type:`rifts`,icon:`🎆`,min:5,each:3e3,multiplier:+e,list:this.listRifts.bind(this),add:this.addRift.bind(this)},{type:`disturbed-burials`,icon:`💀`,min:20,each:3e3,multiplier:+e,list:this.listDisturbedBurial.bind(this),add:this.addDisturbedBurial.bind(this)},{type:`necropolises`,icon:`🪦`,min:20,each:1e3,multiplier:1,list:this.listNecropolis.bind(this),add:this.addNecropolis.bind(this)},{type:`encounters`,icon:`🧙`,min:10,each:600,multiplier:1,list:this.listEncounters.bind(this),add:this.addEncounter.bind(this)},{type:`party`,icon:`🚩`,size:46,pin:`pin`,fill:`#ffffff`,stroke:`#d4351c`,min:1,each:2**53-1,multiplier:1,list:this.listParty.bind(this),add:this.addParty.bind(this)}].map(e=>({...e,icon:Oe.glyph(e.icon)}))}resetConfig(){this.config=this.getDefaultConfig()}generateTypes(){this.config.forEach(({type:e,icon:t,dx:n,dy:r,px:i,size:a,pin:o,fill:s,stroke:c,min:l,each:u,multiplier:d,list:f,add:p})=>{if(d===0)return;let m=Array.from(f(pack)),h=this.getQuantity(m,l,u,d);for(;h&&m.length;){let[l]=this.extractAnyElement(m),u=this.addMarker({icon:t,type:e,dx:n,dy:r,px:i,size:a,pin:o,fill:s,stroke:c},{cell:l});u&&(p(u,l),h--)}}),this.occupied=[]}getQuantity(e,t,n,r){if(!e.length||e.length<t/r)return 0;let i=Math.ceil(e.length/n*r);return Math.min(e.length,i)}extractAnyElement(e){let t=Math.floor(Math.random()*e.length);return e.splice(t,1)}addMarker(e,t){let{cell:n}=t;if(n===void 0)return;let r=rt(pack.markers)?.i+1||0,[i,a]=this.getMarkerCoordinates(n),o=t.type??e.type,s={...e,x:i,y:a,...t,cell:n,i:r,name:t.name||Ci(o),tags:t.tags??[]};return pack.markers.push(s),this.occupied[n]=!0,s}getMarkerCoordinates(e){let{cells:t,burgs:n}=pack,r=t.burg[e];if(r){let{x:e,y:t}=n[r];return[e,t]}return t.p[e]}listVolcanoes({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=70)}addVolcano(e,t){let{cells:n}=pack,r=A.getCulture(n.culture[t]),i=O(.3)?`Mount ${r}`:O(.7)?`${r} Volcano`:r,a=O(.6)?`Dormant`:O(.4)?`Active`:`Erupting`;e.name=i,e.note=`${a} volcano. Height: ${sn(n.p[t],pack,grid)}.`}listHotSprings({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>50&&e.culture[t])}addHotSpring(e,t){let{cells:n}=pack,r=A.getCulture(n.culture[t]),i=ln(Mt(35,15,20,100)),a=O(.3)?`Hot Springs of ${r}`:O(.7)?`${r} Hot Springs`:r,o=`A geothermal springs with naturally heated water that provide relaxation and medicinal benefits. Average temperature is ${i}.`;e.name=a,e.note=o}listWaterSources({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>30&&e.r[t])}addWaterSource(e,t){let{cells:n}=pack,r=T(zr);e.name=`${A.getCulture(n.culture[t])} ${r}`,e.note=`This legendary water source is whispered about in ancient tales and believed to possess mystical properties. The spring emanates crystal-clear water, shimmering with an otherworldly iridescence that sparkles even in the dimmest light.`}getMinedGood(e){let t=g.get(pack.cells.good[e]);if(t?.tags.some(e=>e===`ore`||e===`mineral`))return pack.burgs[pack.cells.burg[e]]?.production?.some(e=>!en(e)&&!nn(e)&&e.goodId===t.i)?t:void 0}getMarketGoods(e){let t=pack.cells.market?.[e],n=rn.get(t);if(!n)return new Set;let r=Object.keys(n.goods).filter(e=>n.goods[+e].stock>0).map(Number);for(let{good:e,seller:n,sellerType:i,buyer:a,buyerType:o}of pack.deals??[])(i===`market`&&n===t||o===`market`&&a===t)&&r.push(e);return new Set(r.map(e=>g.get(e)?.name).filter(e=>e!==void 0))}listMines({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.burg[t]&&this.getMinedGood(t))}addMine(e,t){let{cells:n}=pack,i=this.getMinedGood(t)?.name.toLowerCase()??`ore`,a=pack.burgs[n.burg[t]],o=`${a.name} — ${i} mining town`,s=r(a.population*options.map.units.population.scale*options.map.units.population.urbanization.rate),c=`${a.name} is a mining town of ${s} people just nearby the ${i} mine.`;e.name=o,e.note=c}listBridges({cells:e,burgs:t}){let n=Et(e.fl.filter(e=>e));return e.i.filter(r=>!this.occupied[r]&&e.burg[r]&&e.t[r]!==1&&t[e.burg[r]].population>20&&e.r[r]&&e.fl[r]>n)}addBridge(e,t){let{cells:n}=pack,r=pack.burgs[n.burg[t]],i=pack.rivers.find(e=>e.i===pack.cells.r[t]),a=i?`${i.name} ${i.type}`:`river`,o=i&&O(.2)?`${i.name} Bridge`:`${r.name} Bridge`,s=O(.7)?`A ${T(Br)} bridge spans over the ${a} near ${r.name}.`:`An old crossing of the ${a}, rarely used since ${D(Vr)}.`;e.name=o,e.note=s}listInns({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.pop[t]>5&&_.isCrossroad(t))}addInn(e,t){let n=O(.3)?`inn`:`tavern`,r=O(.7),i=D(Ur),a=r?O(.6)?`${D(Hr)} ${i}`:`${D(Wr)} ${i}`:`${D(Wr)} ${s(n)}`,o=this.getMarketGoods(t),c=e=>Object.entries(e).flatMap(([e,t])=>o.has(e)?t:[]),l=(e,t)=>e.length&&O(.7)?D(e):D(t),u=grid.cells.temp[pack.cells.g[t]]>=18?[...qr,...Jr]:qr,d=c(Kr),f=[...u,...d].includes(i.toLowerCase()),p=r&&f&&O(.5)?i:l(d,u),m=`A big and famous roadside ${n}. Delicious ${`${D(Gr)} ${p}`.toLowerCase()} with ${`${O(.5)?D(Yr):D(Hr)} ${l(c(Xr),Zr)}`.toLowerCase()} is served here.`;e.name=`The ${a}`,e.note=m}listLighthouses({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.harbor[t]>6&&e.c[t].some(t=>e.h[t]<20&&_.isConnected(t)))}addLighthouse(e,t){let{cells:n}=pack,r=n.burg[t]?pack.burgs[n.burg[t]].name:A.getCulture(n.culture[t]);e.name=`${k(r)} Lighthouse`,e.note=`A lighthouse to serve as a beacon for ships in the open sea.`}listWaterfalls({cells:e}){return e.i.filter(t=>e.r[t]&&!this.occupied[t]&&e.h[t]>=50&&e.c[t].some(t=>e.h[t]<40&&e.r[t]))}addWaterfall(e,t){let{cells:n}=pack,r=n.burg[t]?pack.burgs[n.burg[t]].name:A.getCulture(n.culture[t]);e.name=`${k(r)} Waterfall`,e.note=D(Qr)}listBattlefields({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.state[t]&&e.pop[t]>2&&e.h[t]<50&&e.h[t]>25)}addBattlefield(e,t){let{cells:n,states:r}=pack,i=r[n.state[t]];i.campaigns||=z.generateCampaign(i);let a=D(i.campaigns),o=Si(a.start,a.end),s=`${A.getCulture(n.culture[t])} Battlefield`,c=`A historical battle of the ${a.name}. \r\nDate: ${o} ${options.map.lore.calendar.era}.`;e.name=s,e.note=c}listDungeons({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.pop[t]&&e.pop[t]<3)}addDungeon(e,t){let n=`${options.map.seed}${t}`,r=`<div>Undiscovered dungeon. See <a href="https://watabou.github.io/one-page-dungeon/?seed=${n}" target="_blank">One page dungeon</a></div><iframe style="pointer-events: none;" src="https://watabou.github.io/one-page-dungeon/?seed=${n}" sandbox="allow-scripts allow-same-origin"></iframe>`;e.name=`Dungeon`,e.note=r}listLakeMonsters({features:e}){return e.filter(e=>e.type===`lake`&&e.subtype===`freshwater`&&!this.occupied[e.firstCell]).map(e=>e.firstCell)}addLakeMonster(e,t){let n=pack.features[pack.cells.f[t]];if(n.type!==`lake`)return;let r=`${n.name} Monster`,i=Mt(10,5,5,100),a=`${D($r)} say a relic monster of ${i} ${options.map.units.height.unit} long inhabits ${n.name} Lake. Truth or lie, folks are afraid to fish in the lake.`;e.name=r,e.note=a}listSeaMonsters({cells:e,features:t}){return e.i.filter(n=>!this.occupied[n]&&e.h[n]<20&&_.isConnected(n)&&t[e.f[n]].type===`ocean`)}addSeaMonster(e,t){let n=`${A.getCultureShort(0)} Monster`,r=`Old sailors tell stories of a gigantic sea monster inhabiting these dangerous waters. Rumors say it can be ${Mt(25,10,10,100)} ${options.map.units.height.unit} long.`;e.name=n,e.note=r}listHillMonsters({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=50&&e.pop[t])}addHillMonster(e,t){let{cells:n}=pack,r=D(ti),i=A.getCulture(n.culture[t]),a=`${i} ${r}`,o=`${D($r)} speak of a ${D(ei)} ${r} who inhabits ${i} hills and ${D(ni)}.`;e.name=a,e.note=o}listSacredMountains({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=70&&e.c[t].some(t=>e.culture[t])&&e.c[t].every(t=>e.h[t]<60))}addSacredMountain(e,t){let{cells:n,religions:r}=pack,i=n.c[t].map(e=>n.culture[e]).find(e=>e),a=n.religion[t]||n.c[t].map(e=>n.religion[e]).find(e=>e),o=`${A.getCulture(i)} Mountain`,s=sn(n.p[t],pack,grid),c=`A sacred mountain${a?` of ${r[a].name}`:``}. Height: ${s}.`;e.name=o,e.note=c}listSacredForests({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.religion[t]&&[6,8].includes(e.biome[t]))}addSacredForest(e,t){let{cells:n,religions:r}=pack,i=n.culture[t],a=n.religion[t],o=`${A.getCulture(i)} Forest`,s=`A forest sacred to local ${r[a].name}.`;e.name=o,e.note=s}listSacredPineries({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.religion[t]&&e.biome[t]===9)}addSacredPinery(e,t){let{cells:n,religions:r}=pack,i=n.culture[t],a=n.religion[t],o=`${A.getCulture(i)} Pinery`,s=`A pinery sacred to local ${r[a].name}.`;e.name=o,e.note=s}listSacredPalmGroves({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.religion[t]&&e.biome[t]===1&&e.pop[t]>1&&_.isConnected(t))}addSacredPalmGrove(e,t){let{cells:n,religions:r}=pack,i=n.culture[t],a=n.religion[t],o=`${A.getCulture(i)} Palm Grove`,s=`A palm grove sacred to local ${r[a].name}.`;e.name=o,e.note=s}listBrigands({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&_.hasRoad(t))}addBrigands(e,t){let{cells:n}=pack,r=n.culture[t],i=n.biome[t],a=((e,t)=>e>=70?`highlander`:[1,2].includes(t)?`desert`:[3,4].includes(t)?`mounted`:[5,6,7,8,9].includes(t)?`forest`:t===12?`swamp`:`angry`)(n.h[t],i),o=`${A.getCulture(r)} ${D(ri)}`,s=`A gang of ${a} ${T(ii)}.`;e.name=o,e.note=s}listPirates({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]<20&&_.isConnected(t))}addPirates(e,t){e.name=`Pirates`,e.note=`Pirate ships have been spotted in these waters.`}listStatues({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=20&&e.h[t]<40)}addStatue(e,t){let{cells:n}=pack,r=n.culture[t],i=D(ai),a=`${A.getCulture(r)} ${i}`,o=oi[D(Object.keys(oi))],s=Array(E(40,100)).fill(null).map(()=>D(o.split(``))).join(``),c=`An ancient ${i.toLowerCase()}. It has an inscription, but no one can translate it:
        <div style="font-size: 1.8em; line-break: anywhere;">${s}</div>`;e.name=a,e.note=c}listRuins({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.h[t]>=20&&e.h[t]<60)}addRuins(e,t){let n=D(si),r=`Ruined ${n}`,i=`Ruins of an ancient ${n.toLowerCase()}. Untold riches may lie within.`;e.name=r,e.note=i}listLibraries({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.burg[t]&&e.pop[t]>10)}addLibrary(e,t){let{cells:n}=pack,r=T(ci);e.name=`${A.getCulture(n.culture[t])} ${r}`,e.note=`A vast collection of knowledge, including many rare and ancient tomes.`}listCircuses({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.culture[t]&&e.h[t]>=20&&_.isConnected(t))}addCircus(e,t){let n=D(li),r=`Travelling ${n} Circus`,i=`Roll up, roll up, this ${n.toLowerCase()} circus is here for a limited time only.`;e.name=r,e.note=i}listJousts({cells:e,burgs:t}){return e.i.filter(n=>!this.occupied[n]&&e.burg[n]&&t[e.burg[n]].population>20)}addJoust(e,t){let{cells:n,burgs:r}=pack;if(!n.burg[t])return;let i=r[n.burg[t]].name,a=D(ui),o=D(di),s=`${i} ${a}`,c=`Warriors from around the land gather for a ${a.toLowerCase()} of ${o} in ${i}, with fame, fortune and favour on offer to the victor.`;e.name=s,e.note=c}listFairs({cells:e,burgs:t}){return e.i.filter(n=>!this.occupied[n]&&e.burg[n]&&t[e.burg[n]].population<20&&t[e.burg[n]].population>5)}addFair(e,t){let{cells:n,burgs:r}=pack;if(!n.burg[t])return;let i=r[n.burg[t]],a=i.name,o=(i.production??[]).flatMap(e=>en(e)?[]:[e]).sort((e,t)=>t.units-e.units).map(e=>g.get(e.goodId)?.name.toLowerCase()).filter(e=>e!==void 0),s=[...new Set(o)].slice(0,3),c=s.length?`offering local ${Dt(s)} alongside foreign goods and services`:`with all manner of local and foreign goods and services on offer`,l=`${a} Fair`,u=`A fair is being held in ${a}, ${c}.`;e.name=l,e.note=u}listCanoes({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.r[t])}addCanoe(e,t){let n=pack.rivers.find(e=>e.i===pack.cells.r[t]),r=`A small location along the ${n?`${n.name} ${n.type}`:`river`} to launch boats from sits here, along with a weary looking owner, willing to sell passage along the river.`;e.name=`Minor Jetty`,e.note=r}listMigrations({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=20&&e.pop[t]<=2&&Rr[e.biome[t]])}addMigration(e,t){let n=D(Rr[pack.cells.biome[t]]??[`Birds`]),r=`${n} migration`,i=`A huge group of ${n.toLowerCase()} are migrating, whether part of their annual routine, or something more extraordinary.`;e.name=r,e.note=i}listDances({cells:e,burgs:t}){return e.i.filter(n=>!this.occupied[n]&&e.burg[n]&&t[e.burg[n]].population>15)}addDances(e,t){let{cells:n,burgs:r}=pack,i=r[n.burg[t]].name,a=D(fi),o=`${i} ${a}`,s=`A ${a} has been organised at ${i} as a chance to gather the ${D(pi)} of the area together to be merry, make alliances and scheme around the crisis.`;e.name=o,e.note=s}listMirage({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.biome[t]===1)}addMirage(e,t){let n=D(mi),r=`${n} mirage`,i=`This ${n.toLowerCase()} mirage has been luring travellers out of their way for eons.`;e.name=r,e.note=i}listCaves({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=50&&e.pop[t])}addCave(e,t){let{cells:n}=pack,r=T(hi),i=A.getCulture(n.culture[t]);n.biome[t]===11&&(r=`Glacial ${r}`);let a=`${i} ${r}`,o=`The ${a}. Locals claim that it is ${T(gi)}.`;e.name=a,e.note=o}listPortals({burgs:e}){return e.slice(1,Math.ceil(e.length/10)+1).filter(({cell:e})=>!this.occupied[e]).map(e=>e.cell)}addPortal(e,t){let{cells:n,burgs:r}=pack;n.burg[t]&&(e.name=`${r[n.burg[t]].name} Portal`,e.note=`An element of the magic portal system connecting major cities. The portals were installed centuries ago, but still work fine.`)}listRifts({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.pop[t]<=3&&pack.biomes[e.biome[t]].habitability)}addRift(e,t){let n=D(_i),r=`${n} Rift`,i=`A rumoured ${n.toLowerCase()} rift in this area is causing ${D(vi)}.`;e.name=r,e.note=i}listDisturbedBurial({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=20&&e.pop[t]>2)}addDisturbedBurial(e,t){e.name=`Disturbed Burial`,e.note=`A burial site has been disturbed in this area, causing the dead to rise and attack the living.`}listNecropolis({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=20&&e.pop[t]<2)}addNecropolis(e,t){let{cells:n}=pack,r=`${A.getCulture(n.culture[t])} ${T(yi)}`,i=D(bi);e.name=r,e.note=i}listEncounters({cells:e}){return e.i.filter(t=>!this.occupied[t]&&e.h[t]>=20&&e.pop[t]>1)}addEncounter(e,t){if(typeof navigator>`u`||navigator.onLine!==!1){let n=`<div>You have encountered a character.</div><iframe src="https://deorum.vercel.app/encounter/${t}" width="375" height="600" sandbox="allow-scripts allow-same-origin allow-popups"></iframe>`;e.name=`Random encounter`,e.note=n;return}let{cells:n}=pack,r=A.getCulture(n.culture[t]),i=(pack.biomes[n.biome[t]]?.name||`wilderness`).toLowerCase(),{subject:a,verb:o}=D(xi),s=`${a} of ${r}`,c=`${a} ${o} in the ${i} of ${r} lands.`;e.name=s,e.note=c}},Di=new Tr(`Generation Pipeline`,[{id:`grid`,run:({graph:e})=>R.prepare(e)},{id:`heightmap`,run:()=>zn.generate()},{id:`markupGrid`,run:()=>x.markupGrid()},{id:`depressionLakes`,run:()=>R.addDeepDepressionLakes()},{id:`nearSeaLakes`,run:()=>R.openNearSeaLakes()},{id:`mapSize`,run:()=>Pe.generate()},{id:`temperatures`,run:()=>Vn.generate()},{id:`precipitation`,run:()=>st.generate()},{id:`clearPack`,run:()=>S.clear()},{id:`clearGraphOverride`,run:()=>pn.clear()},{id:`regraph`,run:()=>S.generate()},{id:`markupPack`,run:()=>x.markupPack()},{id:`defaultRuler`,run:()=>Ln.createDefaultRuler()},{id:`rivers`,run:()=>we.generate()},{id:`biomes`,run:()=>Rn.generate()},{id:`featureGroups`,run:()=>x.defineGroups()},{id:`ice`,run:()=>Bn.generate()},{id:`goods`,run:()=>g.generate()},{id:`rankCells`,run:()=>he.rankCells()},{id:`cultures`,run:()=>de.generate()},{id:`culturesExpand`,run:()=>de.expand()},{id:`burgs`,run:()=>ge.generate()},{id:`states`,run:()=>z.generate()},{id:`routes`,run:()=>_.generate()},{id:`religions`,run:()=>Ir.generate()},{id:`burgsSpecify`,run:()=>ge.specify()},{id:`stateStatistics`,run:()=>z.collectStatistics()},{id:`stateForms`,run:()=>z.defineStateForms()},{id:`provinces`,run:()=>tn.generate()},{id:`provincePoles`,run:()=>tn.getPoles()},{id:`riversSpecify`,run:()=>we.specify()},{id:`featureNames`,run:()=>x.defineNames()},{id:`markets`,run:()=>rn.generate()},{id:`production`,run:()=>an.produce()},{id:`taxes`,run:()=>z.collectTaxes()},{id:`military`,run:()=>ke.generate()},{id:`markers`,run:()=>Ei.generate()},{id:`zones`,run:()=>Er.generate()},{id:`addedLabels`,run:()=>In.initiate()},{id:`journeys`,run:()=>Hn.generate()},{id:`legends`,run:()=>_t.initiate()}]),Oi=new Tr(`Erase Heightmap`,[{id:`markupGrid`,run:()=>x.markupGrid()},{id:`depressionLakes`,run:({erosion:e})=>e&&R.addDeepDepressionLakes()},{id:`nearSeaLakes`,run:({erosion:e})=>e&&R.openNearSeaLakes()},{id:`temperatures`,run:()=>Vn.generate()},{id:`precipitation`,run:()=>st.generate()},{id:`regraph`,run:()=>S.generate()},{id:`markupPack`,run:()=>x.markupPack()},{id:`rivers`,run:({erosion:e})=>we.generate(e)},{id:`biomes`,run:()=>Rn.define()},{id:`featureGroups`,run:()=>x.defineGroups()},{id:`ice`,run:()=>Bn.generate()},{id:`goods`,run:()=>g.generate()},{id:`rankCells`,run:()=>he.rankCells()},{id:`cultures`,run:()=>de.generate()},{id:`culturesExpand`,run:()=>de.expand()},{id:`burgs`,run:()=>ge.generate()},{id:`states`,run:()=>z.generate()},{id:`routes`,run:()=>_.generate()},{id:`religions`,run:()=>Ir.generate()},{id:`burgsSpecify`,run:()=>ge.specify()},{id:`stateStatistics`,run:()=>z.collectStatistics()},{id:`stateForms`,run:()=>z.defineStateForms()},{id:`provinces`,run:()=>tn.generate()},{id:`provincePoles`,run:()=>tn.getPoles()},{id:`riversSpecify`,run:()=>we.specify()},{id:`featureNames`,run:()=>x.defineNames()},{id:`markets`,run:()=>rn.generate()},{id:`production`,run:()=>an.produce()},{id:`taxes`,run:()=>z.collectTaxes()},{id:`military`,run:()=>ke.generate()},{id:`markers`,run:()=>Ei.generate()},{id:`zones`,run:()=>Er.generate()}]);function ki(){w.eraseAll();for(let e of N(`deftemp`).querySelectorAll(`path, clipPath, svg`))e.remove();lt(),N(`coas`).innerHTML=``,dt(),at.releaseAll()}var Ai=`standard`;function ji(e){Ai=e}var Mi=()=>Ai!==`standard`,Ni=()=>Ai===`globe`,Pi=`fmg-help-token`,Fi=`fmg-help-signin-pending`,Ii=`#token=`,Li=()=>localStorage.getItem(Pi),Ri=e=>localStorage.setItem(Pi,e),zi=()=>localStorage.removeItem(Pi);function Bi(){if(!location.hash.startsWith(Ii))return;let e=sessionStorage.getItem(Fi)===`1`;sessionStorage.removeItem(Fi),e&&Ri(location.hash.slice(7)),history.replaceState(null,``,location.pathname+location.search)}function Vi(e){sessionStorage.setItem(Fi,`1`),location.assign(e)}var Hi=6e4;function Ui(){let e=Date.now();async function t(){let t=options.app.autosave.interval;if(t&&!options.map.viewOnly&&!((Date.now()-e)/Hi<t)){if(options.app.mode)return I(u(`Autosave: map cannot be saved in edit mode`),!1,`warn`,2e3);try{I(u(`Autosave: saving map...`),!1,`warn`,3e3),await B.Save.writeToStorage(await B.Save.prepareMapData()),I(u(`Autosave: map is saved`),!1,`success`,2e3),e=Date.now()}catch(e){h.error(e),I(u(`Autosave failed: {{error}}`,{error:e?.message||u(`Unknown error`)}),!0,`error`,4e3)}}}setInterval(t,Hi/2),Ki()}var Wi,Gi=!1;function Ki(){if(!options.app.autosave.remind)return;let e=[u(`Please don't forget to save the project to desktop from time to time`),u(`Please remember to save the map to your desktop`),u(`Saving will ensure your data won't be lost in case of issues`),u(`Safety is number one priority. Please save the map`),u(`Don't forget to save your map on a regular basis!`),u(`Just a gentle reminder for you to save the map`),u(`Please don't forget to save your progress (saving to desktop is the best option)`),u(`Don't want to get reminded about need to save? Press CTRL+Q`)];Wi=setInterval(()=>{options.app.mode||I(D(e),!0,`warn`,2500)},15*Hi),Gi=!0}function qi(){Gi?(I(u(`Save reminder is turned off. Press CTRL+Q again to re-initiate`),!0,`warn`,2e3),clearInterval(Wi),b.set(e=>e.app.autosave.remind=!1),Gi=!1):(I(u(`Save reminder is turned on. Press CTRL+Q to turn off`),!0,`warn`,2e3),b.set(e=>e.app.autosave.remind=!0),Ki())}var Ji={"#terrs #landHeights":`#terrs > #landHeights`,"#terrs #oceanHeights":`#terrs > #oceanHeights`},Yi={"#map":{path:[`map`],options:{"data-filter":`dataFilter`},drop:[`background-color`]},"#armies":{path:[`military`],options:{"box-size":`boxSize`},drop:[`font-size`]},"#biomes":{path:[`biomes`],drop:[`mask`]},"#cells":{path:[`cells`],rename:{opacity:`stroke-opacity`}},"#gridOverlay":{path:[`grid`],options:{type:`type`,scale:`scale`,dx:`dx`,dy:`dy`}},"#coordinates":{path:[`coordinates`],rename:{"data-size":`font-size`},drop:[`font-size`]},"#compass":{path:[`compass`],drop:[`shape-rendering`]},"#compass > use":{path:[`compass`,`groups`,`compassRose`]},"#rivers":{path:[`rivers`]},"#freshwater":{path:[`lakes`,`groups`,`freshwater`]},"#salt":{path:[`lakes`,`groups`,`salt`]},"#sinkhole":{path:[`lakes`,`groups`,`sinkhole`]},"#frozen":{path:[`lakes`,`groups`,`frozen`]},"#lava":{path:[`lakes`,`groups`,`lava`]},"#dry":{path:[`lakes`,`groups`,`dry`]},"#sea_island":{path:[`coastline`,`groups`,`sea_island`],drop:[`auto-filter`,`stroke-dasharray`,`stroke-linecap`]},"#lake_island":{path:[`coastline`,`groups`,`lake_island`],drop:[`stroke-dasharray`,`stroke-linecap`]},"#terrs > #landHeights":{path:[`heightmap`,`groups`,`landHeights`],options:{scheme:`scheme`,terracing:`terracing`,skip:`skip`,relax:`relax`,curve:`curve`}},"#terrs > #oceanHeights":{path:[`heightmap`,`groups`,`oceanHeights`],options:{scheme:`scheme`,terracing:`terracing`,skip:`skip`,relax:`relax`,curve:`curve`,"data-render":`render`},bools:[`render`]},"#terrain":{path:[`relief`],options:{set:`set`,size:`size`,density:`density`}},"#relig":{path:[`religions`]},"#cults":{path:[`cultures`]},"#statesBody":{path:[`states`,`groups`,`statesBody`]},"#statesHalo":{path:[`states`,`groups`,`statesHalo`],rename:{"data-width":`stroke-width`},drop:[`stroke-width`]},"#provs":{path:[`provinces`],drop:[`data-size`,`fill`,`font-size`,`font-family`]},"#zones":{path:[`zones`]},"#stateBorders":{path:[`borders`,`groups`,`stateBorders`]},"#provinceBorders":{path:[`borders`,`groups`,`provinceBorders`]},"#roads":{path:[`routes`,`groups`,`roads`]},"#trails":{path:[`routes`,`groups`,`trails`]},"#searoutes":{path:[`routes`,`groups`,`searoutes`]},"#journeys":{path:[`journeys`]},"#temperature":{path:[`temperature`],rename:{opacity:`stroke-opacity`}},"#ice":{path:[`ice`]},"#prec":{path:[`precipitation`]},"#population":{path:[`population`]},"#rural":{path:[`population`,`groups`,`rural`]},"#urban":{path:[`population`,`groups`,`urban`]},"#emblems":{path:[`emblems`]},"#texture":{path:[`texture`],options:{"data-href":`href`,"data-x":`x`,"data-y":`y`}},"#goodsCells":{path:[`goods`,`groups`,`goodsCells`]},"#goodsIcons":{path:[`goods`,`groups`,`goodsIcons`],options:{"data-size":`size`,"data-circle":`circle`},bools:[`circle`]},"#goodsBurgs":{path:[`goods`,`groups`,`goodsBurgs`],options:{"data-size":`size`}},"#markets":{path:[`markets`],options:{"data-size":`size`,"font-size":`iconSize`,"data-icon":`icon`},strings:[`icon`],drop:[`opacity`,`fill`]},"#tradeAnimation":{path:[`trade`]},"#markers":{path:[`markers`],drop:[`rescale`]},"#ruler":{path:[`rulers`],rename:{"data-size":`font-size`}},"#scaleBar":{path:[`scaleBar`],options:{"data-bar-size":`barSize`,"data-x":`x`,"data-y":`y`,"data-label":`label`},strings:[`label`]},"#scaleBarBack":{path:[`scaleBar`,`groups`,`back`],options:{"data-top":`top`,"data-right":`right`,"data-bottom":`bottom`,"data-left":`left`}},"#legend":{path:[`legend`],options:{"data-columns":`columns`},rename:{"data-size":`font-size`},drop:[`data-x`,`data-y`]},"#legendBox":{path:[`legend`,`groups`,`box`]},"#fogging":{path:[`fogging`]},"#vignette":{path:[`vignette`]},"#vignette-rect":{path:[`vignette`],options:{x:`x`,y:`y`,width:`width`,height:`height`,rx:`rx`,ry:`ry`,filter:`filter`},ownAttrs:!1},"#oceanLayers":{path:[`ocean`,`groups`,`oceanLayers`],options:{layers:`outline`},strings:[`outline`]},"#oceanBase":{path:[`ocean`,`groups`,`base`]},"#oceanicPattern":{path:[`ocean`,`groups`,`pattern`]},"#landmass":{path:[`landmass`]}},Xi=Object.keys(H.defaults.routes.groups),Zi=Object.keys(H.defaults.lakes.groups),Qi=new Set([`fill`,`stroke`,`color`,`shore`]),$i=Object.keys(Object.values(H.defaults.labels.groups)[0].attrs),ea=Object.keys(Object.values(H.defaults.burgIcons.groups)[0].groups.icons.attrs);async function ta(e,t){let n=t?a(t):void 0;return n&&na(n),ia(e,{hasStyleRecord:!!n}),JSON.stringify(styles)}function na(e){let t=typeof e==`object`&&e?e:{};if(t.labels?.groups&&(styles.labels.groups=Object.fromEntries(Object.entries(t.labels.groups).map(([e,t])=>[e,Da(t)]))),t.burgIcons||t.anchors){let e=styles.burgIcons.groups,n=new Set([...Object.keys(t.burgIcons??{}),...Object.keys(t.anchors??{})]);for(let r of n)e[r]={groups:{icons:Aa(t.burgIcons?.[r]),anchors:ja(t.anchors?.[r])}}}t.relief&&(styles.relief.options={...styles.relief.options,set:Te.sets.find(e=>e===t.relief?.set)??`simple`,size:Va(t.relief.size,1),density:Va(t.relief.density,.4)})}function ra(e=document){let t={};for(let[n,r]of Object.entries(la())){let i=Yi[n],a=i.ownAttrs===!1?[]:za(i.path),o=e.querySelector(n);if(o)t[n]=fa(o,r,a);else{let r=ua(i,e),o=r?a.filter(e=>r.hasAttribute(e)):[];o.length&&(t[n]=Object.fromEntries(o.map(e=>[e,null])))}}for(let n of e.querySelectorAll(`#labels > *`)){let e=n.dataset.group||n.id.replace(/^labels-/,``);e&&(t[`#labels > #${e}`]=fa(n,[...$i,`data-dx`,`data-dy`,`data-size`],$i))}for(let n of e.querySelectorAll(`#routes > g`))n.id&&(n.dataset.group=n.id),n.id&&!Xi.includes(n.id)&&(t[`#routes > g#${n.id}`]=fa(n,Object.keys(Object.values(H.defaults.routes.groups)[0].attrs)));for(let n of e.querySelectorAll(`#lakes > g`))n.id&&(n.dataset.group=n.id),n.id&&!Zi.includes(n.id)&&(t[`#lakes > g#${n.id}`]=fa(n,Object.keys(H.defaults.lakes.groups.freshwater.attrs),[]));for(let n of e.querySelectorAll(`#burgIcons > g`))n.id&&(t[`#burgIcons > g#${n.id}`]=fa(n,[...ea,`font-size`,`size`,`data-icon`],ea));for(let n of e.querySelectorAll(`#anchors > g`))n.id&&(t[`#anchors > g#${n.id}`]=fa(n,[...ea,`font-size`,`size`,`data-icon`],ea));for(let n of[`stateEmblems`,`provinceEmblems`,`burgEmblems`]){let r=e.querySelector(`#emblems > #${n}`);r&&(t[`#emblems > #${n}`]=fa(r,[`data-size`],[]))}return Ea(t,{onUnknown:`skip`})}function ia(e,{hasStyleRecord:t=!1}={}){let n=ra(e);n.labels=structuredClone(styles.labels),t&&Object.keys(styles.burgIcons.groups).length&&(n.burgIcons.groups=structuredClone(styles.burgIcons.groups)),n.relief.options=structuredClone(styles.relief.options);let r={regions:[n.states.groups.statesBody],terrs:Object.values(n.heightmap.groups),lakes:Object.values(n.lakes.groups),coastline:Object.values(n.coastline.groups),borders:Object.values(n.borders.groups),routes:Object.values(n.routes.groups),labels:Object.values(n.labels.groups),burgIcons:Object.values(n.burgIcons.groups).map(e=>e.groups.icons),anchors:Object.values(n.burgIcons.groups).map(e=>e.groups.anchors)};for(let[t,n]of Object.entries(r)){let r=e.getElementById(t)?.getAttribute(`opacity`);if(r!=null)for(let e of n)e.attrs.opacity=Number(r)||null}e.getElementById(`legend`)?.hasAttribute(`data-columns`)||(n.legend.options.columns=styles.legend.options.columns);for(let t of[`stateEmblems`,`provinceEmblems`,`burgEmblems`])e.getElementById(t)?.hasAttribute(`data-size`)||(n.emblems.groups[t].options=structuredClone(styles.emblems.groups[t].options));e.getElementById(`goodsIcons`)?.hasAttribute(`data-size`)||(n.goods.groups.goodsIcons.options.size=styles.goods.groups.goodsIcons.options.size),e.getElementById(`goodsBurgs`)?.hasAttribute(`data-size`)||(n.goods.groups.goodsBurgs.options=structuredClone(styles.goods.groups.goodsBurgs.options)),e.getElementById(`markets`)?.hasAttribute(`data-size`)||(n.markets.options.size=styles.markets.options.size);for(let t of[`landHeights`,`oceanHeights`])e.getElementById(t)?.hasAttribute(`scheme`)||(n.heightmap.groups[t].options=structuredClone(styles.heightmap.groups[t].options));e.getElementById(`armies`)?.hasAttribute(`box-size`)||(n.military.options=structuredClone(styles.military.options)),e.getElementById(`gridOverlay`)?.hasAttribute(`type`)||(n.grid.options=structuredClone(styles.grid.options)),e.getElementById(`markets`)?.hasAttribute(`font-size`)||(n.markets.options.iconSize=styles.markets.options.iconSize),e.getElementById(`markets`)?.hasAttribute(`data-icon`)||(n.markets.options.icon=styles.markets.options.icon),e.getElementById(`goodsIcons`)?.hasAttribute(`data-circle`)||(n.goods.groups.goodsIcons.options.circle=styles.goods.groups.goodsIcons.options.circle),e.getElementById(`texture`)?.hasAttribute(`data-href`)||(n.texture.options=structuredClone(styles.texture.options)),e.getElementById(`oceanLayers`)?.hasAttribute(`layers`)||(n.ocean.groups.oceanLayers.options.outline=styles.ocean.groups.oceanLayers.options.outline),e.getElementById(`scaleBar`)?.hasAttribute(`data-bar-size`)||(n.scaleBar.options=structuredClone(styles.scaleBar.options)),e.getElementById(`scaleBarBack`)?.hasAttribute(`data-top`)||(n.scaleBar.groups.back.options=structuredClone(styles.scaleBar.groups.back.options));for(let t of w.all){let r=n[t.id]?.attrs,i=styles[t.id]?.attrs;if(!r||!i)continue;let a=e.getElementById(t.elementId);for(let e of Object.keys(t.params.attrs??{}))e in r&&!a?.hasAttribute(e)&&(r[e]=i[e])}Ca(n),H.set(n)}function aa(e){if(e in Yi)return Yi[e];let t=e.match(/^#labels > #(.+)$/);if(t)return{path:[`labels`,`groups`,t[1]],kind:`label`};let n=e.match(/^#burgIcons > g#(.+)$/);if(n)return{path:[`burgIcons`,`groups`,n[1],`groups`,`icons`],kind:`burg`};let r=e.match(/^#anchors > g#(.+)$/);if(r)return{path:[`burgIcons`,`groups`,r[1],`groups`,`anchors`],kind:`anchor`};let i=e.match(/^#routes > g#(.+)$/);if(i)return{path:[`routes`,`groups`,i[1]],kind:`route`};let a=e.match(/^#lakes > g#(.+)$/);if(a)return Yi[`#${a[1]}`]??{path:[`lakes`,`groups`,a[1]],kind:`lake`};let o=e.match(/^#emblems > #(.+)$/);if(o)return{path:[`emblems`,`groups`,o[1]],options:{"data-size":`size`}}}function oa(e,t){if(e===`skip`)h.warn(t);else throw Error(t)}function sa(e,t,n,r,i){n.options&&!e.options&&(e.options={});let a=e.options,o={};for(let[e,r]of Object.entries(t))e!==`id`&&!n.drop?.includes(e)&&(o[e]=r);for(let[e,t]of Object.entries(n.rename??{}))e in o&&(o[t]=o[e],delete o[e]);let s={};for(let[e,t]of Object.entries(n.options??{})){if(!(e in o))continue;let c=qa(o[e]);delete o[e],t in s&&s[t]!==c?oa(i,`unknown legacy attribute "${e}" on "${r}" conflicts for option "${t}"`):(s[t]=c,a&&(a[t]=n.bools?.includes(t)?!!Number(c):n.strings?.includes(t)&&c!=null?String(c):c))}if(e.attrs&&n.ownAttrs!==!1)for(let t of Object.keys(o))t in e.attrs&&(e.attrs[t]=Ja(t,o[t]),delete o[t]);for(let e of Object.keys(o))oa(i,`unknown legacy attribute "${e}" on "${r}"`)}function ca(e){let t=Ne(H.defaults,e);return t?.attrs?Object.keys(t.attrs):[]}function la(){let e={};for(let[t,n]of Object.entries(Yi)){let r=n.ownAttrs===!1?[]:ca(n.path);e[t]=[...new Set([...r,...Object.keys(n.options??{}),...Object.keys(n.rename??{}),...n.drop??[]])]}return e}function ua(e,t){if(e.path.length<2)return null;let n=w.all.find(({id:t})=>t===e.path[0]);return n?t.querySelector(`#${n.elementId}`):null}function da(e){if(e===``)return``;let t=Number(e);return Number.isNaN(t)?e:t}function fa(e,t,n=t){let r={};for(let i of t){let t=e.style?.[i],a=typeof t==`string`&&t?t:e.getAttribute(i);if(a!=null){let e=da(a);r[i]=Qi.has(i)&&typeof e==`string`?Lt(e):e}else n.includes(i)&&(r[i]=null)}return r}function pa(e,...t){for(let n of t){if(!Ta(e)){let t=e[n];if(t)return t;continue}let t=aa(n),r=t&&Ne(e,t.path);if(r?.attrs)return r.attrs}}function ma(e,t){let n=(e,t={})=>{let n=new Set([`id`,`style`,`data-layer`,`data-group`,...Object.keys(t)]);return Array.from(e.attributes).every(e=>n.has(e.name))},r=(t,r,i)=>{let a=e.getElementById(t);if(r&&a?.tagName===`g`&&n(a,i))for(let[e,n]of Object.entries(r))n!==null&&n!==`null`&&(t===`terrain`&&[`set`,`size`,`density`].includes(e)||a.setAttribute(e,String(n)))};for(let e of w.all){r(e.elementId,pa(t,`#${e.elementId}`),e.params.attrs);for(let n of e.children)r(n.id,pa(t,`#${n.id}`,`#${e.elementId} > #${n.id}`),n.attrs)}}var ha=new Set([`filter`,`mask`,`stroke-dasharray`]),ga=new Set([`stroke-linecap`,`stroke-linejoin`]),_a={"map.attrs.filter":oe,"ocean.groups.pattern.attrs.href":Un},va=(e,t)=>{let n=Number.parseFloat(t);return Number.isFinite(n)?`${n}${e[0]===`labels`&&e[1]===`groups`?`%`:`px`}`:t},W=e=>typeof e==`object`&&e?e:void 0,ya={borders:[`stateBorders`,`provinceBorders`],coastline:[`sea_island`,`lake_island`],compass:[`compassRose`],emblems:[`stateEmblems`,`provinceEmblems`,`burgEmblems`],goods:[`goodsCells`,`goodsIcons`,`goodsBurgs`],heightmap:[`landHeights`,`oceanHeights`],legend:[`box`],ocean:[`base`,`pattern`,`oceanLayers`,`oceanWaves`],population:[`rural`,`urban`],scaleBar:[`back`],states:[`statesBody`,`statesHalo`]};function ba(e){let t=(e,t)=>{let n=W(e[t]);return n||(n={},e[t]=n),n};for(let[n,r]of Object.entries(ya)){let i=W(e[n]);if(!i)continue;let a=t(i,`groups`);for(let e of r)i[e]!==void 0&&(a[e]=i[e],delete i[e])}let n=W(e.burgIcons);if(!n)return;let r=W(n.burgIcons)?.groups,i=W(n.anchors)?.groups;if(!r&&!i)return;let a=t(n,`groups`),o=e=>t(t(a,e),`groups`);for(let[e,t]of Object.entries(r??{}))o(e).icons=t;for(let[e,t]of Object.entries(i??{}))o(e).anchors=t;delete n.burgIcons,delete n.anchors}function xa(e){let t=W(e);if(!t)return;ba(t);let n=e=>typeof e==`number`?`${e}px`:e,r=e=>e.attrs??={},i=(e,t,n,i=e=>e)=>{let a=W(e),o=a?.options;a&&o&&(o[t]!==void 0&&(r(a)[n]=i(o[t])),delete o[t],Object.keys(o).length||delete a.options)},a=(e,t,n)=>{let r=W(e);r&&r[t]!==void 0&&(r[n]=r[t],delete r[t])};i(t.map,`dataFilter`,`filter`,e=>e?`url(#filter-${e})`:null);let o=W(t.ocean);if(o){let e=W(o.groups);if(e||(e={},o.groups=e),o.options&&`pattern`in o.options){let{pattern:t,patternOpacity:n}=o.options;e.pattern={attrs:{href:t,opacity:n??1}},delete o.options.pattern,delete o.options.patternOpacity}}i(W(W(t.states)?.groups)?.statesHalo,`width`,`stroke-width`);let s=W(t.military);s?.options&&delete s.options.fontSize,s?.attrs&&delete s.attrs[`font-size`];let c=W(t.labels);c&&delete c.attrs,i(t.coordinates,`fontSize`,`font-size`,n),i(t.rulers,`fontSize`,`font-size`,n),i(t.legend,`fontSize`,`font-size`,n);let l=W(t.legend)?.options;if(l)for(let e of[`x`,`y`])delete l[e];let u=W(t.scaleBar);u?.attrs&&(u.attrs[`font-size`]=n(u.attrs[`font-size`]??10)),a(W(t.temperature)?.attrs,`opacity`,`stroke-opacity`),a(W(t.cells)?.attrs,`opacity`,`stroke-opacity`);let d=W(t.biomes);d?.attrs&&delete d.attrs.mask,a(W(t.markets)?.options,`fontSize`,`iconSize`);let f=W(t.markers);f&&delete f.options;let p=W(W(W(t.coastline)?.groups)?.sea_island);p&&delete p.options;for(let e of[`sea_island`,`lake_island`]){let n=W(W(W(t.coastline)?.groups)?.[e])?.attrs;if(n)for(let e of[`stroke-dasharray`,`stroke-linecap`])delete n[e]}let m=W(t.markets)?.attrs;if(m)for(let e of[`fill`,`opacity`])delete m[e];let h=W(t.compass)?.attrs;h&&delete h[`shape-rendering`];let ee=W(W(W(t.heightmap)?.groups)?.landHeights);ee?.options&&delete ee.options.render}function Sa(e){typeof e==`object`&&e&&xa(e);let t=(e,n,r)=>{if(typeof e==`object`&&e)for(let[i,a]of Object.entries(e)){if(typeof a==`object`){t(a,[...n,i],i===`attrs`||i===`options`);continue}if(!r||typeof a!=`string`)continue;let o=a.trim(),s=_a[[...n,i].join(`.`)];e[i]=s?o in s?o:null:ha.has(i)&&o===``||ga.has(i)&&o===`inherit`?null:i===`font-size`?va(n,o):i===`icon`&&(n[0]===`burgIcons`||n[0]===`markets`)?Na(Fa(o)??``):o}};return t(e,[],!1),Ca(e),e}function Ca(e){let t=(e,n)=>{if(typeof e==`object`&&e)for(let[r,i]of Object.entries(e))typeof i==`object`?t(i,r===`attrs`||r===`options`):n&&typeof i==`string`&&Qi.has(r)&&(e[r]=Lt(i))};t(e,!1)}function wa(e){return Object.keys(e).some(e=>e.startsWith(`#`))}function Ta(e){return typeof e==`object`&&!!e&&`map`in e}function Ea(e,t={}){let n=t.onUnknown??`throw`,r=structuredClone(H.defaults);for(let[t,i]of Object.entries(e)){let e=Ji[t]??t,a=aa(e);if(!a){oa(n,`unknown legacy selector "${e}"`);continue}if(a.kind){if(a.kind===`burg`||a.kind===`anchor`){let e=a.path[2],t=r.burgIcons.groups,n=t[e]??structuredClone(t.town??Object.values(t)[0]);a.kind===`burg`?n.groups.icons=Aa(i):n.groups.anchors=ja(i),t[e]=n;continue}let t=Ne(r,a.path.slice(0,-1));if(!t){oa(n,`unknown legacy selector "${e}"`);continue}let o=a.kind===`label`?Da:a.kind===`lake`?La:Ia;t[a.path.at(-1)]=o(i);continue}let o=Ne(r,a.path);o?sa(o,i,a,e,n):oa(n,`unknown legacy selector "${e}"`)}return H.parse(Sa(r))}function Da(e){let t=e,n=G(t.opacity,1);return{attrs:{opacity:n===0?1:n,fill:K(t.fill,`#3e3e4b`),"fill-opacity":G(t[`fill-opacity`],null),stroke:K(t.stroke,`#3a3a3a`),"stroke-opacity":G(t[`stroke-opacity`],null),"stroke-width":G(t[`stroke-width`],0)??0,"stroke-dasharray":K(t[`stroke-dasharray`],null),"stroke-linecap":Ka(t[`stroke-linecap`],Ha),"stroke-linejoin":Ka(t[`stroke-linejoin`],Ua),"letter-spacing":G(t[`letter-spacing`],0),"font-size":K(t[`data-size`],null)??K(t[`font-size`],`18%`)??`18%`,"font-family":K(t[`font-family`],`Almendra SC`)??`Almendra SC`,"font-style":Ka(t[`font-style`],Wa),"font-weight":Ka(G(t[`font-weight`],null),be),"text-decoration":Ka(t[`text-decoration`],Ga),style:Oa(t),filter:K(t.filter,null)}}}function Oa(e){let t=Va(e[`data-dx`],0),n=Va(e[`data-dy`],0),r=t||n?`transform: translate(${t}em, ${n}em)`:``;return ka([K(e.style,null),r].filter(Boolean).join(`; `))}function ka(e){return(e||``).split(`;`).map(e=>e.trim()).filter(e=>e&&!/^display\s*:/.test(e)).join(`; `)||null}function Aa(e){let t=e??{};return{attrs:{opacity:G(t.opacity,null),fill:K(t.fill,null),"fill-opacity":G(t[`fill-opacity`],null),stroke:K(t.stroke,null),"stroke-opacity":G(t[`stroke-opacity`],null),"stroke-width":G(t[`stroke-width`],null),"stroke-dasharray":K(t[`stroke-dasharray`],null),"stroke-linecap":Ka(t[`stroke-linecap`],Ha),"stroke-linejoin":Ka(t[`stroke-linejoin`],Ua),filter:K(t.filter,null)},options:{size:Va(t[`font-size`],Va(t.size,1)),icon:Na(Fa(K(t[`data-icon`],null))??`burgs-atlas-circle`)}}}function ja(e){let t=Aa(e);return t.options.icon===`burgs-atlas-circle`&&(t.options.icon=`ports-anchor`),t}function Ma(e){if(Ee.fileOf(e))return!0;let t=Ee.setForId(e);return(t?Ee.get(t).aliases?.(Ee.files(t))??[]:[]).some(({name:n})=>Ee.symbolId(t,n)===e)}function Na(e){let t=e.trim(),n=t.startsWith(`#`)?t.slice(1):t;return Oe.glyphText(n)!==null||Oe.kind(n)===`custom`||Ma(n)?n:Oe.glyph(t)}function Pa(e){let t=new Map;for(let n of e){let e=n.icon;if(!e)continue;if(!St(e)){n.icon=Na(e);continue}let r=t.get(e);r||(r=Se.add({kind:`image`,content:e,viewBox:je}).id,t.set(e,r)),n.icon=r}}function Fa(e){let t=e?.match(/^#icon-(.+)$/)?.[1];return t?t===`anchor`||t===`harbor`?`ports-${t}`:t.startsWith(`watabou-`)||t.startsWith(`illustrated-`)?`burgs-${t}`:`burgs-atlas-${t}`:e}function Ia(e){let t=e;return{attrs:{opacity:G(t.opacity,null),stroke:K(t.stroke,null),"stroke-opacity":G(t[`stroke-opacity`],null),"stroke-width":G(t[`stroke-width`],null),"stroke-dasharray":K(t[`stroke-dasharray`],null),"stroke-linecap":Ka(t[`stroke-linecap`],Ha),"stroke-linejoin":Ka(t[`stroke-linejoin`],Ua),filter:K(t.filter,null),mask:Ka(t.mask,[`url(#land)`,`url(#water)`])}}}function La(e,t=H.defaults.lakes.groups.freshwater){let n=structuredClone(t),r=n.attrs;for(let[t,n]of Object.entries(e))t in r&&(r[t]=Ja(t,n));return n}function Ra(e,t){return La(fa(e,Object.keys((t??H.defaults.lakes.groups.freshwater).attrs),[]),t)}function za(e){let t=Wn;for(let n of[...e,`attrs`])t=Ba(t)?.shape?.[n];let n=Ba(t)?.shape;return n?Object.keys(n).filter(e=>n[e].safeParse(null).success):[]}var Ba=e=>typeof e==`object`&&e?e:void 0;function Va(e,t){let n=Number(e);return Number.isFinite(n)?n:t}function G(e,t){return e===void 0?t:e===null?null:Va(e,0)}function K(e,t){return e===void 0||e===``?t:e===null?null:String(e)}var Ha=Object.keys(Re),Ua=Object.keys(me),Wa=Object.keys(Ve),Ga=Object.keys(re);function Ka(e,t){return t.includes(e)?e:null}function qa(e){return e===`null`?null:e}function Ja(e,t){return[`stroke-dasharray`,`font-size`].includes(e)&&typeof t==`number`?String(t):qa(t)}function Ya(e){let t=t=>{let n=Number(e.get(t));return Number.isFinite(n)&&n>0?n:void 0};return{width:t(`width`),height:t(`height`)}}var Xa={};function Za(e){Object.assign(Xa,e)}function Qa(e=options.app.ui.assistant===`show`){let t=M(`assistantBubble`);t&&(t.style.display=e?`flex`:`none`)}function $a(e){let t=M(`assistantBubble`);t?.classList.toggle(`open`,e),t?.setAttribute(`aria-expanded`,String(e))}var eo=/(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-/]))?/,to=()=>new URL(window.location.href).searchParams;async function no(){let e=to(),t=Ya(e),n=e.get(`maplink`);if(n){if(h.warn(`Load map from URL`),eo.test(n)){setTimeout(()=>B.Load.loadMapFromURL(n,!0),1e3);return}B.Load.showUploadErrorMessage(u(`Map link is not a valid URL`),n)}if(e.get(`seed`))h.warn(`Generate map for seed`,e.get(`seed`)),await ro(t);else{if(options.app.onLoad===`lastSaved`)try{let e=await ve.get(`lastMap`);if(e){h.warn(`Loading last stored map`),B.Load.uploadMap(e);return}}catch(e){h.error(e)}h.warn(`Generate random map`),ro(t)}}async function ro(e){await L.StylePresetsEditor.applyOnLoad(),await Xa.generate(e),Xa.applyLayersPreset(),w.drawAll(),Pn(),io(),Qa()}function io(){let e=to();if(Xa.applyURLLayers(e),e.get(`from`)===`MFCG`&&document.referrer){let t=e.get(`seed`)??``;if(t.length===13)e.set(`burg`,t.slice(-4));else{ao(e);return}}let t=e.get(`scale`),n=e.get(`cell`),r=e.get(`burg`);if(!t&&!n&&!r)return;let i=+(t??0)||8;if(n){let[e,t]=pack.cells.p[+n];Cn(e,t,i,1600)}else if(r){let e=Number.isNaN(+r)?pack.burgs.find(e=>e.name===r):pack.burgs[+r];e&&Cn(e.x,e.y,i,1600)}else Cn(+(e.get(`x`)??0)||options.map.graph.width/2,+(e.get(`y`)??0)||options.map.graph.height/2,i,1600)}function ao(e){let{cells:t}=pack,n=pack.burgs;if(n.length<2)return void h.error(`Cannot select a burg for MFCG`);let r=+(e.get(`size`)??0),i=+(e.get(`coast`)??0),a=+(e.get(`port`)??0),o=+(e.get(`river`)??0),s=(e,r,i)=>r&&i?n.filter(e=>e.port&&t.r[e.cell]):!r&&e&&i?n.filter(e=>!e.port&&t.t[e.cell]===1&&t.r[e.cell]):!e&&!i?n.filter(e=>t.t[e.cell]!==1&&!t.r[e.cell]):!e&&i?n.filter(e=>t.t[e.cell]!==1&&t.r[e.cell]):e&&i?n.filter(e=>t.t[e.cell]===1&&t.r[e.cell]):[],c=s(i,a,o);c.length||(c=s(i,!a,!o)),c.length||(c=s(!i,0,!o)),c.length||(c=[n[1]]);let l=e=>Math.abs((e.population??0)-r),d=Ft(c,(e,t)=>l(e)-l(t)),f=d===void 0?0:c[d].i;if(!f)return void h.error(`Cannot select a burg for MFCG`);let p=n[f];for(let[e,t]of new URL(document.referrer).searchParams)e===`name`?p.name=t:e===`size`?p.population=+t:e===`seed`?p.MFCG=t:e===`shantytown`?p.shanty=+t:p[e]=+t;let m=e.get(`name`);m&&m!==`null`&&(p.name=m);let ee=P(`#labels [data-label-type='burg'][data-id='${f}']`);ee.empty()||ee.text(p.name??``).classed(`drag`,!0).on(`mouseover`,function(){P(this).classed(`drag`,!1),ee.on(`mouseover`,null)}),Cn(p.x,p.y,8,1600),I(u(`Here stands the glorious city of {{burg}}`,{burg:p.name}),!0,`success`,15e3)}function oo(){let e=!document.querySelectorAll(`i.icon-lock`).length,t=`?seed=${N(`seedInput`).value}&width=${options.map.graph.width}&height=${options.map.graph.height}${e?`&options=default`:``}`;navigator.clipboard.writeText(location.host+location.pathname+t).then(()=>I(u(`Map URL is copied to clipboard`),!1,`success`,3e3)).catch(e=>I(u(`Could not copy URL: {{error}}`,{error:String(e)}),!1,`error`,5e3))}var so=e=>{let{parentNode:t,host:n,defaultView:r}=e,i=t||n||r;return i?[e,...so(i)]:[e]};function co(e){let t=e.currentTarget;if(!t||!pack.cells?.p)return;let n=Ht(e,t),r=S.findCell(n[0],n[1]);if(r===void 0)return;uo(e);let i=R.findCell(n[0],n[1]);M(`tooltip`)?.dataset.main?Zt():po(n,e,r,i)}var lo=null;function uo(e){if(M(`notesEditor`))return;let t=le.resolveTarget(e.target instanceof Element?e.target:null),n=t&&le.key(t),r=t&&mn.get(t);if(t&&r){if(lo===n)return;lo=n??null;let e=M(`notes`);e&&(e.style.display=`block`);let i=M(`notesHeader`);i&&(i.textContent=le.getName(t));let a=M(`notesBody`);a&&(a.innerHTML=r);return}if(options.app.notesPinned||M(`markerEditor`)||e.shiftKey)return;let i=M(`notes`);i&&(i.style.display=`none`);let a=M(`notesHeader`);a&&(a.innerHTML=``);let o=M(`notesBody`);o&&(o.innerHTML=``),lo=null}function fo(e){let[t,r]=un(e,pack);return u(`Cell population: {{total}}; Rural: {{rural}}; Urban: {{urban}}`,{total:n(t+r),rural:n(t),urban:n(r)})}function po(e,t,n,r){I(``);let i=t.target,a=t.composedPath?t.composedPath():so(i);if(!a[a.length-8])return;let o=a[a.length-7].id,s=pack.cells.h[n]>=20,c=mo({group:o,target:i,event:t,path:a,cellId:n});c===void 0?yo(e,n,r,s):I(c)}function q(e,t=u(`Click to edit`)){return options.map.viewOnly?e||void 0:e?m(e,t):t}function mo({group:e,target:t,event:r,path:i,cellId:a}){let o=t.parentNode,s=t.closest(`[data-label-type='burg'][data-id], #burgIcons [data-id]`);if(s){let e=Number(s.dataset.id),t=pack.burgs[e];if(!t)return q();let r=n((t.population||0)*options.map.units.population.scale*options.map.units.population.urbanization.rate),i={burg:t.name,group:t.group,population:r},a=t.port?u(`{{burg}} {{group}} port`,i):u(`{{burg}} {{group}}`,i);return q(m(a,`${u(`Population`)}: ${r}`))}let c=t.closest(`#labels [data-label-type]`);if(c)return q(p(ho(c)));if(e===`armies`)return q(p(o.dataset.name??``));if(e===`emblems`&&t.tagName===`use`)return go(t,o,r);if(e===`rivers`){let e=le.resolveTarget(t);return q(p(e?le.getName(e):``))}if(e===`routes`){let e=le.resolveTarget(t);if(e&&le.get(e)){let t=le.getName(e);return q(t?p(t):void 0)}}else{if(e===`terrain`||e===`ice`)return q();if(e===`markers`)return q(void 0,u(`Click to edit the Marker. Hold Shift to not close the assosiated note`));if(e===`ruler`)return M(`measurersEditor`)?u(`Drag the measurer or its points to edit`):u(`Measurers Editor`);if(e===`markets`)return _o(t)??``;if(e===`goods`)return vo(t,a)??``;if(e===`lakes`&&pack.cells.h[a]<20){let e=pack.features[Number(t.dataset.f)],n=e?.name?[p(e.name)]:[],r=e?.subtype||`lake`;return q(m(...n,ne[r]??r))}if(e===`zones`){let e=Number(i[i.length-8].dataset.id);return pack.zones.find(t=>t.i===e)?.name}if(e===`journeys`){let e=t.id?.match(/^segment(\d+)_(\d+)$/);if(e){let t=pack.journeys?.find(t=>t.i===+e[1]),n=t?.segments?.find(t=>t.i===+e[2]);if(t&&n){let e=p(`${t.name}: ${n.name}`);return q(n.note?m(e,`“${p(n.note)}”`):e)}}return q()}}}function ho(e){let t=e.querySelectorAll(`tspan`);return(t.length?Array.from(t,e=>e.textContent??``).join(` `):e.textContent??``).replaceAll(`|`,` `).trim()}function go(e,t,n){let[r,i]=t.id===`burgEmblems`?[pack.burgs,`burg`]:t.id===`provinceEmblems`?[pack.provinces,`province`]:[pack.states,`state`],a=r[Number(e.dataset.i)];n.shiftKey&&Kt(i,a),P(e).raise(),P(t).raise();let o=`fullName`in a&&a.fullName||a.name,s=u(i===`burg`?`{{name}} burg emblem`:i===`province`?`{{name}} province emblem`:`{{name}} state emblem`,{name:o});return q(m(s,u(`Hold Shift to show associated area or place`)))}function _o(e){let t=e.closest(`[data-id]`);if(!t)return;let n=rn.get(Number(t.dataset.id)),r=n&&pack.burgs[n.centerBurgId];if(r)return q(u(`{{burg}} market`,{burg:r.name}),u(`Click to view`))}function vo(e,t){let n=pack.cells.good[t],r=e=>Object.entries(e).filter(([e])=>g.get(Number(e))?.visible).map(([e,t])=>`${(g.get(Number(e))?.name||`unknown`).toLowerCase()} ${t}${Number(e)===n?` (bonus)`:``}`).join(`, `);if(e.closest(`#goodsIcons`)){let t=g.get(Number(e.closest(`[data-i]`)?.dataset.i));return q(u(`{{good}} bonus resource`,{good:t?.name}),u(`Click to open Goods Editor and select displayed goods`))}if(e.closest(`#goodsCells`)){let e=an.getCellProduction(t,g.getBiomesProduction());return q(u(`Cell rural production: {{production}}`,{production:r(e)}),u(`Click to select displayed goods in Goods Editor`))}if(e.closest(`#goodsBurgs`)){let t=e.closest(`[data-id]`),n=t&&pack.burgs[Number(t.dataset.id)];return!n||n.removed?void 0:(P(t).raise(),q(u(`{{burg}} urban production: {{production}}`,{burg:n.name,production:r(an.getBurgProduction(n))}),u(`Click to view`)))}}function yo(e,t,n,r){let{cells:i}=pack;if(w.isOn(`precipitation`)&&r)return void I(u(`Annual Precipitation: {{value}}`,{value:cn(t,pack,grid)}));if(w.isOn(`population`))return void I(fo(t));if(w.isOn(`temperature`))return void I(`${u(`Temperature`)}: ${ln(grid.cells.temp[n])}`);if(w.isOn(`biomes`)&&i.biome[t]){let e=i.biome[t];I(`${u(`Biome`)}: ${p(pack.biomes[e].name)}`)}else if(w.isOn(`religions`)&&i.religion[t]){let e=i.religion[t],n=pack.religions[e],r=n.name;if(n.type===`Cult`)return void I(`${u(`Cult`)}: ${p(r)}`);if(n.type===`Heresy`)return void I(`${u(`Heresy`)}: ${p(r)}`);if(n.type===`Folk`)return void I(`${u(`Folk religion`)}: ${p(r)}`);I(`${u(`Organized religion`)}: ${p(r)}`)}else if(i.state[t]&&(w.isOn(`provinces`)||w.isOn(`states`))){let e=i.state[t],n=i.province[t],r=n?`${pack.provinces[n].fullName}, `:``;I(r+pack.states[e].fullName)}else if(w.isOn(`cultures`)&&i.culture[t]){let e=i.culture[t],n=pack.cultures[e],r=n?.ancestry?.trim(),a=r?`${n.name} (${r})`:n?.name||``;I(`${u(`Culture`)}: ${p(a)}`)}else{if(w.isOn(`cells`))return void I(`${u(`Cell`)}: ${t} (${u(`Grid`)}: ${n})`);if(w.isOn(`heightmap`))return void I(`${u(`Height`)}: ${sn(e,pack,grid)}`)}}var bo=$e(co,100);function xo(){An(),P(`#viewbox`).style(`cursor`,`default`).on(`.drag`,null).on(`click`,Do).on(`contextmenu`,Oo).on(`touchmove mousemove`,bo),P(`#legend`).on(`mousemove`,()=>I(m(u(`Drag to change the position`),u(`Click to hide the legend box`)))).on(`click`,So).call(Gt().on(`start`,it)),P(`#scaleBar`).on(`mousemove`,()=>I(u(`Units Editor`))).on(`click`,()=>L.UnitsEditor.open())}function So(e){let t=gt(e)?.dataset.legend;t&&ht.hide(t)}var Co={rivers:e=>L.RiverEditor.open(e.id),ice:e=>L.IceEditor.open(e),terrain:e=>L.ReliefEditor.open(e),goodsCells:()=>L.GoodsEditor.open()},wo={emblems:e=>L.EmblemsEditor.open(void 0,void 0,void 0,e),routes:e=>L.RouteEditor.open(e.id),journeys:(e,t)=>L.JourneyEditor.open(Number(t.id.replace(`journey`,``))),markers:e=>L.MarkersEditor.open(void 0,e),ruler:()=>L.MeasurersEditor.open(),goodsIcons:()=>L.GoodsEditor.open(),goodsBurgs:(e,t)=>L.ProductionOverview.open(Number(t.dataset.id)),lakes:e=>L.LakesEditor.open(e),tradeAnimation:(e,t)=>L.TradeDetails.open(P(t).datum()),markets:(e,t)=>{e.tagName!==`path`&&L.MarketOverview.open(Number(t.dataset.id))}},To={burgIcons:e=>L.BurgEditor.open(Number(e.dataset.id)),markers:e=>L.MarkersEditor.open(void 0,e),ruler:()=>L.MeasurersEditor.open(),armies:(e,t)=>L.RegimentEditor.open(`#${t.id}`)};function Eo(e){let t=e,n=t.parentElement,r=n?.parentElement,i=r?.parentElement,a=i?.parentElement;if(!n||!r||!i||!a)return!1;let o=t.closest(`#labels text[data-label-type]`);if(o){let e=Number(o.dataset.id),t=o.dataset.labelType;return t===`burg`?M(`burgEditor`)?.dataset.burgId===String(e)?L.LabelsEditor.open(t,e):L.BurgEditor.open(e):L.LabelsEditor.open(t,e),!0}let s=Co[n.id]||wo[r.id]||To[i.id];return s?.(t,n),!!s}function Do(e){e?.target&&!options.map.viewOnly&&Eo(e.target)}function Oo(e){e.shiftKey||options.app.mode||options.map.viewOnly||(e.preventDefault(),L.ContextMenu.open(e))}async function ko(){Bi(),vn(),hr(),hn(),b.restore(),await b.restoreIcons(),Pa(options.map.military.units),Es(),nc(),yt(options.map.graph.width,options.map.graph.height),xo(),Cr()||(lr(),await no()),Ui()}async function Ao(e){try{let{seed:t,graph:n,width:r,height:i,points:a,jitter:o}=e||{};b.setGraphSize(r,i),dr(t),b.randomize(),Oe.syncCustom(),n&&(a!==void 0&&(options.map.graph.points=a),o!==void 0&&(options.map.graph.jitter=o),options.map.graph.sampling=n.sampling),Fn(),await Di.run({graph:n}),b.persist(),Es(),dn(),wn()}catch(e){h.error(e),$t(),F.message({message:`${u(`An error has occurred on map generation. Please retry.`)}<br>${u(`If error is critical, clear the stored data and try again.`)}
      <p id="errorBox">${tt(e)}</p>`,title:u(`Generation error`),width:`32em`,buttons:[{label:u(`Cleanup data`),onClick:()=>(yn(),!1)},{label:u(`Regenerate`),onClick:()=>{jo(`generation error`)}},{label:u(`Ignore`)}]})}}var jo=$e(async e=>{let t=typeof e==`string`?e:`user request`;h.warn(`Generate new random map: ${t}`);let n=fe(options.generation.graph.density)>1e4;n&&cr(),F.closeAll(`#worldConfigurator, #options3d`),options.app.mode=null,kn(1e3),ki(),await Ao(typeof e==`string`?void 0:e),w.drawAll(),Mi()&&L.View3d.redraw(),M(`worldConfigurator`)?.offsetParent&&L.WorldConfigurator.open(),Pn(),n&&lr(),$t()},250);function Mo(e){if(options.app.mode){I(u(`New map cannot be generated when edit mode is active, please exit the mode and retry`),!1,`error`);return}let t=fn.at(-1);(t?(Date.now()-t.registeredAt)/6e4:0)<1?jo(e):F.confirm({title:u(`Generate New Map`),message:`${u(`Are you sure you want to generate a new map?`)}<br>${u(`All unsaved changes made to the current map will be lost`)}`,confirm:u(`Generate`),onConfirm:()=>{F.closeAll(),jo(e)}})}var No=`advancedOptions`,Po={default:{label:u(`Default`),sampling:`square`,jitter:Xe},organicHexes:{label:u(`Organic hexes`),sampling:`hexPointy`,jitter:.5},pointyHexBoard:{label:u(`Hex board (pointy)`),sampling:`hexPointy`,jitter:0},flatHexBoard:{label:u(`Hex board (flat)`),sampling:`hexFlat`,jitter:0},squareBoard:{label:u(`Square board`),sampling:`square`,jitter:0},isometricBoard:{label:u(`Isometric board`),sampling:`diamond`,jitter:0}};function Fo({sampling:e,jitter:t}){return Object.entries(Po).find(([,n])=>n.sampling===e&&n.jitter===t)?.[0]??`custom`}var J=({label:e,tip:t,control:n,icon:r=``})=>`
  <tr data-tip="${t}">
    <td>${r}</td>
    <td>${e}</td>
    <td>${n}</td>
  </tr>`,Io=(...e)=>`<div class="inline">${e.join(``)}</div>`,Lo=e=>`<i data-locked="0" id="lock_${e}" class="icon-lock-open"></i>`,Ro=(e,t)=>`<slider-input id="${e}" data-option="${e}" ${t}></slider-input>`,zo=(e,t,n=!1)=>`<option value="${e}" ${n?`disabled`:``}>${t}</option>`,Bo=()=>Object.entries(Po).map(([e,{label:t}])=>zo(e,t)).join(``)+zo(`custom`,u(`Custom`),!0),Vo=()=>[J({label:u(`Map size`),tip:u(`Coordinate extent of the next map, fixed for its life. The Viewport size in Options is only how much of it you see. For full-globe maps use aspect ratio 2:1`),icon:`<i data-tip="${u(`Reset to default`)}" id="restoreDefaultMapSize" class="icon-ccw"></i>`,control:Io(`<input id="mapWidthInput" data-option="mapWidth" type="number" min="240" />`,`<span>x</span>`,`<input id="mapHeightInput" data-option="mapHeight" type="number" min="135" />`)}),J({label:u(`Lattice`),tip:u(`Ready-made sampling and jitter pairs. Regular boards need jitter 0`),control:`<select id="graphPreset" data-option="graphPreset">${Bo()}</select>`}),J({label:u(`Sampling`),tip:u(`The lattice the map cells are built on. Square with high jitter is the classic natural look`),control:`<select id="sampling" data-option="sampling">${Ze.map(e=>zo(e,Fe[e])).join(``)}</select>`}),J({label:u(`Jitter`),tip:u(`How far cell centers move off the lattice. 0 keeps perfectly regular cells, higher values look more natural`),control:Ro(`jitter`,`min="0" max="${We}" step="0.05"`)}),J({label:u(`Provinces ratio`),tip:u(`Set what share of eligible burgs in each state will become province centers. Higher values create more provinces`),icon:Lo(`provincesRatio`),control:Ro(`provincesRatio`,`min="0" max="100"`)}),J({label:u(`Size variety`),tip:u(`Define how much states and cultures can vary in size. Defines expansionism value`),icon:Lo(`sizeVariety`),control:Ro(`sizeVariety`,`min="0" max="10" step=".1"`)}),J({label:u(`Growth rate`),tip:u(`Set the growth rate of states and cultures. Determines how much land stays neutral`),icon:Lo(`growthRate`),control:Ro(`growthRate`,`min=".1" max="2" step=".1"`)})].join(``),Ho=()=>[J({label:u(`Autosave interval`),tip:u(`Set autosave interval in minutes. Set 0 to disable autosave. Map is saved to browser memory`),control:Ro(`autosaveInterval`,`min="0" max="60" step="1"`)}),J({label:u(`On load`),tip:u(`Set what Generator should do on load`),control:`
        <select id="onloadBehavior" data-option="onloadBehavior">
          ${zo(`random`,u(`Generate random map`))}
          ${zo(`lastSaved`,u(`Open last saved map`))}
        </select>`}),J({label:u(`Speaker voice`),tip:u(`Select speech synthesis voice to pronounce generated names`),control:Io(`<select id="speakerVoice" data-option="speakerVoice"></select>`,`<span id="speakerTest" data-tip="${u(`Click to test the voice`)}" style="cursor: pointer">🔊</span>`)}),J({label:u(`Emblem shape`),tip:u(`Select emblem shape. Can be changed individually in the Emblem Editor`),control:Io(`<select id="emblemShape" data-option="emblemShape">${Wo()}</select>`,`<svg class="emblemShapePreview" viewBox="0 0 200 210"><path id="emblemShapeImage" /></svg>`)})].join(``),Uo=[[u(`Diversiform`),[[`culture`,u(`Culture-specific`)],[`random`,u(`Culture-random`)],[`state`,u(`State-specific`)]]],[u(`Basic`),[[`heater`,u(`Heater`)],[`spanish`,u(`Spanish`)],[`french`,u(`French`)]]],[u(`Regional`),[[`horsehead`,u(`Horsehead`)],[`horsehead2`,u(`Horsehead Edgy`)],[`polish`,u(`Polish`)],[`hessen`,u(`Hessen`)],[`swiss`,u(`Swiss`)]]],[u(`Historical`),[[`boeotian`,u(`Boeotian`)],[`roman`,u(`Roman`)],[`kite`,u(`Kite`)],[`oldFrench`,u(`Old French`)],[`renaissance`,u(`Renaissance`)],[`baroque`,u(`Baroque`)]]],[u(`Specific`),[[`targe`,u(`Targe`)],[`targe2`,`${u(`Targe`)} 2`],[`pavise`,u(`Pavise`)],[`wedged`,u(`Wedged`)],[`embowed`,u(`Embowed`)]]],[u(`Banner`),[[`flag`,u(`Flag`)],[`pennon`,u(`Pennon`)],[`guidon`,u(`Guidon`)],[`banner`,u(`Banner`)],[`dovetail`,u(`Dovetail`)],[`gonfalon`,u(`Gonfalon`)],[`pennant`,u(`Pennant`)]]],[u(`Simple`),[[`round`,u(`Round`)],[`oval`,u(`Oval`)],[`vesicaPiscis`,u(`Vesica Piscis`)],[`square`,u(`Square`)],[`diamond`,u(`Diamond`)],[`hexagon`,u(`Hexagon`)]]],[u(`Fantasy`),[1,2,3,4,5].map(e=>[`fantasy${e}`,`${u(`Fantasy`)} ${e}`])],[u(`Middle Earth`),[[`noldor`,u(`Noldor`)],[`gondor`,u(`Gondor`)],[`easterling`,u(`Easterling`)],[`erebor`,u(`Erebor`)],[`ironHills`,u(`Iron Hills`)],[`urukHai`,u(`UrukHai`)],[`moriaOrc`,u(`Moria Orc`)]]]];function Wo(){return Uo.map(([e,t])=>`<optgroup label="${e}">${t.map(([e,t])=>zo(e,t)).join(``)}</optgroup>`).join(``)}function Go(){let e=No;return`
    <div id="${e}" class="dialog" style="display: none">
      <style>
        #${e} table { border-collapse: collapse; }
        #${e} th { text-align: left; font-style: italic; padding-top: 0.5em; }
        #${e} td:last-child { width: 13em; }
        #${e} td:last-child > *, #${e} .inline > :is(select, input) { width: 100%; }
        #${e} .inline { display: flex; align-items: center; gap: 0.3em; }
        #${e} slider-input input[type="range"] { flex: 1; }
        #${e} slider-input input[type="number"] { width: 3.5em; }
        #${e} i { cursor: pointer; }
      </style>
      <table>
        <tr><th colspan="3">${u(`Map settings (apply to new maps)`)}</th></tr>
        ${Vo()}
        <tr><th colspan="3">${u(`Interface settings`)}</th></tr>
        ${Ho()}
      </table>
    </div>`}function Ko(){F.closeAll(`#${No}, .stable`),F.open(No,{title:u(`Advanced Options`),width:`auto`,position:{my:`right top`,at:`right-10 top+10`,of:`svg`},buttons:[{label:u(`New Map`),onClick:()=>Mo()}],persistent:!0})}var qo={open:Ko},Jo={quality:{shapeRendering:`geometricPrecision`,stateHalos:!0,viewportRedraw:`continuous`},balance:{shapeRendering:`optimizeSpeed`,stateHalos:!1,viewportRedraw:`continuous`},speed:{shapeRendering:`optimizeSpeed`,stateHalos:!1,viewportRedraw:`settled`}};function Yo(e){let t=Object.keys(e);for(let[n,r]of Object.entries(Jo))if(t.every(t=>r[t]===e[t]))return n;return`custom`}var Xo=new Set;function Zo(e){return Xo.add(e),()=>Xo.delete(e)}function Qo(e){Object.hasOwn(Jo,e)&&es(t=>t.app.performance={...Jo[e]})}function $o(e,t){es(n=>n.app.performance[e]=t)}function es(e){b.set(e),ts();for(let e of Xo)e()}function ts(){let{shapeRendering:e,stateHalos:t}=options.app.performance;M(`viewbox`)?.setAttribute(`shape-rendering`,e);let n=M(`statesHalo`);n&&(n.style.display=t?``:`none`,t&&pack.cells&&!n.childElementCount&&w.draw(`states`))}var Y=`performanceSettings`,ns=Jo.balance,rs=[{key:`shapeRendering`,label:u(`Shape rendering`),tip:u(`SVG shape-rendering hint for the map. Crisp edges drops anti-aliasing. Chromium-based browsers rasterize on the GPU and ignore the hint for speed purposes, so it makes no difference there`),choices:[{value:`geometricPrecision`,label:u(`Geometric precision`)},{value:`auto`,label:u(`Auto`)},{value:`optimizeSpeed`,label:u(`Optimize speed`)},{value:`crispEdges`,label:u(`Crisp edges`)}]},{key:`stateHalos`,label:u(`State halos`),tip:u(`Blurred glow along state borders. It is an SVG blur filter, which is costly on big maps`),choices:[{value:`true`,label:u(`Shown`)},{value:`false`,label:u(`Hidden`)}]},{key:`viewportRedraw`,label:u(`Redraw on zoom`),tip:u(`When labels, icons and relief are redrawn and text re-sized during a zoom or pan. 'After zoom' does it once per gesture: faster on big maps, but new content appears all at once`),choices:[{value:`continuous`,label:u(`While zooming`)},{value:`settled`,label:u(`After zoom`)}]}],is={quality:u(`Quality`),balance:u(`Balance`),speed:u(`Speed`),custom:u(`Custom`)};function as(){F.closeAll(`#${Y}, .stable`),os();let e=Zo(cs);F.open(Y,{title:u(`Performance Settings`),position:{my:`right top`,at:`right-10 top+10`,of:`svg`},onClose:()=>{e(),F.destroy(Y)}})}function os(){F.destroy(Y),N(`dialogs`).insertAdjacentHTML(`beforeend`,us());for(let{key:e}of rs){let t=N(`${Y}_${e}`);t.addEventListener(`change`,()=>ss(e,t.value)),N(`${Y}_${e}Reset`).addEventListener(`click`,()=>ss(e,String(ns[e])))}}function ss(e,t){e===`stateHalos`?$o(e,t===`true`):$o(e,t)}function cs(){let e=options.app.performance;for(let{key:t}of rs)N(`${Y}_${t}`).value=String(e[t]);N(`${Y}Preset`).textContent=ls()}var ls=()=>is[Yo(options.app.performance)];function us(){let e=options.app.performance,t=rs.map(({key:t,label:n,tip:r,choices:i})=>{let a=String(e[t]);return`
      <tr data-tip="${r}">
        <td>${n}</td>
        <td><select id="${Y}_${t}" style="width: 100%">${i.map(e=>`<option value="${e.value}" ${e.value===a?`selected`:``}>${e.label}</option>`).join(``)}</select></td>
        <td>
          <button id="${Y}_${t}Reset" data-tip="${u(`Reset to the Balance preset value`)}"
            style="font-size: .85em; padding: 1px 5px; margin-left: .3em">↺</button>
        </td>
      </tr>`}).join(``);return`
    <div id="${Y}" class="dialog" style="display: none">
      <p data-tip="${u(`The preset on the Options tab these settings amount to`)}" style="margin: 0 0 .5em">
        ${u(`Preset`)}: <b id="${Y}Preset">${ls()}</b>
      </p>
      <table style="border-collapse: collapse; width: 100%">
        <tbody>${t}</tbody>
      </table>
    </div>`}var ds={open:as},fs={"africa-centric":{id:0,name:u(`Africa Centric`)},arabia:{id:1,name:u(`Arabia`)},atlantics:{id:2,name:u(`Atlantics`)},britain:{id:3,name:u(`Britain`)},caribbean:{id:4,name:u(`Caribbean`)},"east-asia":{id:5,name:u(`East Asia`)},eurasia:{id:6,name:u(`Eurasia`)},europe:{id:7,name:u(`Europe`)},"europe-accented":{id:8,name:u(`Europe Accented`)},"europe-and-central-asia":{id:9,name:u(`Europe and Central Asia`)},"europe-central":{id:10,name:u(`Europe Central`)},"europe-north":{id:11,name:u(`Europe North`)},greenland:{id:12,name:u(`Greenland`)},hellenica:{id:13,name:u(`Hellenica`)},iceland:{id:14,name:u(`Iceland`)},"indian-ocean":{id:15,name:u(`Indian Ocean`)},"mediterranean-sea":{id:16,name:u(`Mediterranean Sea`)},"middle-east":{id:17,name:u(`Middle East`)},"north-america":{id:18,name:u(`North America`)},"us-centric":{id:19,name:u(`US-centric`)},"us-mainland":{id:20,name:u(`US Mainland`)},world:{id:21,name:u(`World`)},"world-from-pacific":{id:22,name:u(`World from Pacific`)}},ps=u(`Click to lock the option and always use the current value on new map generation`),ms=u(`Click to unlock the option and allow it to be randomized on new map generation`),hs=e=>e.dataset.ids?e.dataset.ids.split(`,`):[e.id.slice(5)];function gs(e,t){for(let n of e.querySelectorAll(`[data-locked]`)){let e=hs(n);n.addEventListener(`mouseover`,e=>{e.stopPropagation(),I(n.className===`icon-lock`?ms:ps)}),n.addEventListener(`click`,()=>{let r=n.className!==`icon-lock`;for(let n of e)r?v.set(n,t(n)):v.clear(n)})}_s()}function _s(){let e=v.all();for(let t of document.querySelectorAll(`[data-locked]`)){let n=hs(t).some(t=>Object.hasOwn(e,t));t.dataset.locked=n?`1`:`0`,t.className=n?`icon-lock`:`icon-lock-open`}}v.subscribe(_s);var vs={mapWidth:{read:e=>e.generation.graph.width,update:Ps,pin:`mapWidth`,event:`change`},mapHeight:{read:e=>e.generation.graph.height,update:Ps,pin:`mapHeight`,event:`change`},seed:{read:e=>e.map.seed,update:fr,event:`change`},graphPreset:{read:e=>Fo(e.generation.graph),update:Is},sampling:X({read:e=>e.generation.graph.sampling,write:(e,t)=>e.generation.graph.sampling=t,parse:e=>e,effect:()=>Ts(`graphPreset`)}),jitter:X({read:e=>e.generation.graph.jitter,write:(e,t)=>e.generation.graph.jitter=t,parse:Number,effect:()=>Ts(`graphPreset`)}),points:X({read:e=>e.generation.graph.density,write:(e,t)=>e.generation.graph.density=t,parse:Number,pin:`points`,effect:ks}),template:X({read:e=>e.generation.template,write:(e,t)=>e.generation.template=t,parse:String,pin:`template`}),resolveDepressionsSteps:X({read:e=>e.generation.resolveDepressionsSteps,write:(e,t)=>e.generation.resolveDepressionsSteps=t,parse:Number,pin:`resolveDepressionsSteps`}),lakeElevationLimit:X({read:e=>e.generation.lakeElevationLimit,write:(e,t)=>e.generation.lakeElevationLimit=t,parse:Number,pin:`lakeElevationLimit`,effect:()=>options.app.mode===`heightmap`&&L.HeightmapEditor.redrawDrainage()}),cultures:X({read:e=>e.generation.cultures.limit,write:(e,t)=>e.generation.cultures.limit=t,parse:Number,pin:`cultures`,effect:As}),culturesSet:X({read:e=>e.generation.cultures.set,write:(e,t)=>{e.generation.cultures.set=t,b.capCultures()},parse:String,pin:`culturesSet`,effect:As}),statesNumber:X({read:e=>e.generation.states.limit,write:(e,t)=>e.generation.states.limit=t,parse:Number,pin:`statesNumber`}),provincesRatio:X({read:e=>e.generation.provinces.ratio,write:(e,t)=>e.generation.provinces.ratio=t,parse:Number,pin:`provincesRatio`}),religionsNumber:X({read:e=>e.generation.religions.limit,write:(e,t)=>e.generation.religions.limit=t,parse:Number,pin:`religionsNumber`}),manors:X({read:e=>e.generation.burgs.limit,write:(e,t)=>e.generation.burgs.limit=t,parse:Number,pin:`manors`,effect:Os}),sizeVariety:X({read:e=>e.generation.states.sizeVariety,write:(e,t)=>e.generation.states.sizeVariety=e.generation.cultures.sizeVariety=t,parse:Number,pin:`sizeVariety`}),growthRate:X({read:e=>e.generation.states.growthRate,write:(e,t)=>e.generation.states.growthRate=e.generation.cultures.growthRate=t,parse:Number,pin:`growthRate`}),uiSize:X({read:e=>e.app.ui.size,write:(e,t)=>e.app.ui.size=t,parse:Number,effect:zs}),tooltipSize:X({read:e=>e.app.ui.tooltipSize,write:(e,t)=>e.app.ui.tooltipSize=t,parse:Number,effect:Vs}),azgaarAssistant:X({read:e=>e.app.ui.assistant,write:(e,t)=>e.app.ui.assistant=t,parse:e=>e===`hide`?`hide`:`show`,effect:e=>Qa(e===`show`)}),speakerVoice:X({read:e=>e.app.ui.speakerVoice||null,write:(e,t)=>e.app.ui.speakerVoice=t,parse:String}),emblemShape:X({read:e=>e.app.emblems.shape,write:(e,t)=>e.app.emblems.shape=t,parse:String,effect:Rs}),performancePreset:{read:e=>Yo(e.app.performance),update:Qo},onloadBehavior:X({read:e=>e.app.onLoad,write:(e,t)=>e.app.onLoad=t,parse:e=>e===`lastSaved`?`lastSaved`:`random`}),autosaveInterval:X({read:e=>e.app.autosave.interval,write:(e,t)=>e.app.autosave.interval=t,parse:Number}),viewportWidth:{read:()=>vt.width,update:qs,event:`change`},viewportHeight:{read:()=>vt.height,update:qs,event:`change`},zoomExtentMin:{read:e=>e.app.zoomExtent.min,update:Ks,event:`change`},zoomExtentMax:{read:e=>e.app.zoomExtent.max,update:Ks,event:`change`},themeHue:{read:e=>j(e.app.ui.themeColor).h,update:Ws},themeColor:{read:e=>e.app.ui.themeColor,update:e=>Hs(e,options.app.ui.transparency)},transparency:{read:e=>e.app.ui.transparency,update:e=>Hs(options.app.ui.themeColor,+e)}};function X(e){let{read:t,write:n,parse:r,pin:i,effect:a}=e;return{read:t,pin:i,update(e){let t=r(e);b.set(e=>n(e,t)),i&&v.set(i,t),a?.(t)}}}var ys=new Intl.Collator,bs=Object.entries(f).sort(([e,t],[n,r])=>e===`en`?-1:n===`en`?1:ys.compare(t,r)),xs=`
  <p data-tip="${u(`Settings for the next map. Generate a new map to apply them`)}">
    ${u(`Map settings (apply to new maps)`)}:
  </p>
  <table>
    <tr
      data-tip="${u(`Map seed number. Press 'Enter' to apply. A seed reproduces the same map only if the map size and the settings are the same`)}"
    >
      <td>
        <i
          data-tip="${u(`Show seed history to apply a previous seed`)}"
          id="optionsMapHistory"
          class="icon-hourglass-1"
        ></i>
      </td>
      <td>${u(`Map seed`)}</td>
      <td>
        <input id="seedInput" data-option="seed" class="long" type="number" min="1" max="999999999" step="1" />
      </td>
      <td>
        <i
          data-tip="${u(`Copy map seed as URL. It will produce the same map only if options are default or the same`)}"
          id="optionsCopySeed"
          class="icon-docs"
        ></i>
      </td>
    </tr>
    <tr
      data-tip="${u(`Set number of points to be used for graph generation. Highly affects performance. 10K is the only recommended value`)}"
    >
      <td>
        <i data-locked="0" id="lock_points" class="icon-lock-open"></i>
      </td>
      <td>${u(`Points number`)}</td>
      <td>
        <input
          id="pointsInput"
          data-option="points"
          type="range"
          min="1"
          max="13"
          value="4"
          data-cells="10000"
        />
      </td>
      <td>
        <output id="pointsOutputFormatted" data-option-output="points" style="color: #053305">10K</output>
      </td>
    </tr>
    <tr data-tip="${u(`Select template or precreated heightmap to be used on generation`)}">
      <td>
        <i data-locked="0" id="lock_template" class="icon-lock-open"></i>
      </td>
      <td>${u(`Heightmap`)}</td>
      <td id="templateInputContainer" class="pointer">
        <select id="templateInput" data-option="template" style="pointer-events: none"></select>
      </td>
      <td></td>
    </tr>
    <tr data-tip="${u(`Define how many Cultures should be generated`)}">
      <td>
        <i data-locked="0" id="lock_cultures" class="icon-lock-open"></i>
      </td>
      <td>${u(`Cultures number`)}</td>
      <td>
        <input id="culturesInput" data-option="cultures" type="range" min="1" />
      </td>
      <td>
        <input id="culturesOutput" data-option="cultures" type="number" min="1" />
      </td>
    </tr>
    <tr data-tip="${u(`Select a set of cultures to be used for names and cultures generation`)}">
      <td>
        <i data-locked="0" id="lock_culturesSet" class="icon-lock-open"></i>
      </td>
      <td>${u(`Cultures set`)}</td>
      <td>
        <select id="culturesSet" data-option="culturesSet">
          <option value="world" data-max="32" selected>${u(`All-world`)}</option>
          <option value="european" data-max="15">${u(`European`)}</option>
          <option value="oriental" data-max="13">${u(`Oriental`)}</option>
          <option value="english" data-max="10">${u(`English`)}</option>
          <option value="antique" data-max="10">${u(`Antique`)}</option>
          <option value="highFantasy" data-max="17">${u(`High Fantasy`)}</option>
          <option value="darkFantasy" data-max="18">${u(`Dark Fantasy`)}</option>
          <option value="random" data-max="100">${u(`Random`)}</option>
        </select>
      </td>
      <td></td>
    </tr>
    <tr data-tip="${u(`Define how many states and capitals should be generated`)}">
      <td>
        <i data-locked="0" id="lock_statesNumber" class="icon-lock-open"></i>
      </td>
      <td>${u(`States number`)}</td>
      <td colspan="2">
        <slider-input id="statesNumber" data-option="statesNumber" min="0" max="100"></slider-input>
      </td>
    </tr>
    <tr data-tip="${u(`Define a number of non-capital settlements to be placed (if enough suitable land exists)`)}">
      <td>
        <i data-locked="0" id="lock_manors" class="icon-lock-open"></i>
      </td>
      <td>${u(`Number of burgs`)}</td>
      <td>
        <input id="manorsInput" data-option="manors" type="range" min="0" max="1000" step="1" value="1000" />
      </td>
      <td>
        <output id="manorsOutput" data-option-output="manors" value="auto"></output>
      </td>
    </tr>
    <tr
      data-tip="${u(`Define how many organized religions and cults should be generated. Cultures will have their own folk religions in any case`)}"
    >
      <td>
        <i data-locked="0" id="lock_religionsNumber" class="icon-lock-open"></i>
      </td>
      <td>${u(`Religions number`)}</td>
      <td colspan="2">
        <slider-input
          id="religionsNumber"
          data-option="religionsNumber"
          min="0"
          max="50"
          step="1"
        ></slider-input>
      </td>
    </tr>
  </table>
  <p data-tip="${u(`Interface preferences saved in this browser. Changes apply immediately`)}">
    ${u(`Interface settings`)}:
  </p>
  <table>
    <tr data-tip="${u(`Select the interface language. It applies after a reload`)}">
      <td></td>
      <td>${u(`Language`)}</td>
      <td>
        <select id="interfaceLanguage">
          ${bs.map(([e,t])=>`<option value="${e}" ${e===d.language?`selected`:``}>${t}</option>`).join(``)}
        </select>
      </td>
      <td></td>
    </tr>
    <tr
      data-tip="${u(`Set user interface size. Please note browser zoom also affects interface size (Ctrl + or Ctrl - to change)`)}"
    >
      <td></td>
      <td>${u(`Interface size`)}</td>
      <td colspan="2">
        <slider-input id="uiSize" data-option="uiSize" min=".6" max="3" step=".1"></slider-input>
      </td>
    </tr>
    <tr data-tip="${u(`Set tooltip size`)}">
      <td></td>
      <td>${u(`Tooltip size`)}</td>
      <td colspan="2">
        <slider-input id="tooltipSize" data-option="tooltipSize" min="1" max="32" value="14"></slider-input>
      </td>
    </tr>
    <tr data-tip="${u(`Set theme hue for dialogs and tool windows`)}">
      <td>
        <i data-tip="${u(`Reset to default`)}" id="themeColorRestore" class="icon-ccw"></i>
      </td>
      <td>${u(`Theme color`)}</td>
      <td>
        <input id="themeHueInput" data-option="themeHue" type="range" min="0" max="359" />
      </td>
      <td>
        <input id="themeColorInput" data-option="themeColor" type="color" />
      </td>
    </tr>
    <tr data-tip="${u(`Set dialog and tool windows transparency`)}">
      <td></td>
      <td>${u(`Transparency`)}</td>
      <td colspan="2">
        <slider-input id="transparencyInput" data-option="transparency" min="0" max="100"></slider-input>
      </td>
    </tr>
    <tr data-tip="${u(`Rendering preset: visual quality traded for speed. Pick 'Speed' if the map feels slow`)}">
      <td></td>
      <td>${u(`Performance`)}</td>
      <td>
        <select id="performancePreset" data-option="performancePreset">
          <option value="quality">${u(`Quality`)}</option>
          <option value="balance" selected>${u(`Balance`)}</option>
          <option value="speed">${u(`Speed`)}</option>
          <option value="custom" disabled hidden>${u(`Custom`)}</option>
        </select>
      </td>
      <td>
        <i data-tip="${u(`Open the performance settings`)}" id="openPerformanceSettings" class="icon-cog"></i>
      </td>
    </tr>
    <tr data-tip="${u(`Toggle Azgaar Assistant (help bubble on the bottom right corner)`)}">
      <td></td>
      <td>${u(`Azgaar Assistant`)}</td>
      <td>
        <select id="azgaarAssistant" data-option="azgaarAssistant">
          <option value="show" selected>${u(`Show`)}</option>
          <option value="hide">${u(`Hide`)}</option>
        </select>
      </td>
    </tr>
    <tr
      data-tip="${u(`Size of the map window on screen. Independent of the map size: it is how much of the map you see at once. Set by hand it is remembered, until you fit it back to the window`)}"
    >
      <td>
        <i data-tip="${u(`Fit the viewport to the browser window`)}" id="viewportFit" class="icon-ccw"></i>
      </td>
      <td>${u(`Viewport size`)}</td>
      <td>
        <input id="viewportWidth" data-option="viewportWidth" class="paired" type="number" min="100" />
        <span>x</span>
        <input id="viewportHeight" data-option="viewportHeight" class="paired" type="number" min="100" />
        <span>px</span>
      </td>
      <td></td>
    </tr>
    <tr data-tip="${u(`Set minimum and maximum possible zoom level`)}">
      <td>
        <i data-tip="${u(`Reset to default`)}" id="zoomExtentDefault" class="icon-ccw"></i>
      </td>
      <td>${u(`Zoom extent`)}</td>
      <td>
        <span data-tip="${u(`Minimum possible zoom level (should be > 0)`)}">${u(`min`)}</span>
        <input
          data-tip="${u(`Minimum possible zoom level (should be > 0)`)}"
          id="zoomExtentMin" data-option="zoomExtentMin"
          class="paired"
          type="number"
          min=".2"
          step=".1"
          max="20"
          value="1"
        />
        <span data-tip="${u(`Maximum possible zoom level (should be > 1)`)}">${u(`max`)}</span>
        <input
          data-tip="${u(`Maximum possible zoom level (should be > 1)`)}"
          id="zoomExtentMax" data-option="zoomExtentMax"
          class="paired"
          type="number"
          min="1"
          max="50"
          value="20"
        />
      </td>
      <td>
        <i
          data-tip="${u(`Allow dragging the map beyond the canvas borders`)}"
          id="translateExtent"
          data-on="0"
          class="icon-hand-paper-o"
        ></i>
      </td>
    </tr>
  </table>
  <p data-tip="${u(`Open the map configurators or reset all options`)}">${u(`Configure`)}:</p>
  <div style="display: flex; flex-wrap: wrap; gap: 0.3em; margin: 0.3em 0.3em 0">
    <button
      id="configureWorld"
      style="flex: 1; min-width: max-content"
      data-tip="${u(`Open the World Configurator to set the map position on the globe and the world climate`)}"
    >
      ${u(`Climate`)}
    </button>
    <button
      id="setupLore"
      style="flex: 1; min-width: max-content"
      data-tip="${u(`Click to name the map, date its calendar and describe the world`)}"
    >
      ${u(`Lore`)}
    </button>
    <button
      id="openAdvancedOptions"
      style="flex: 1; min-width: max-content"
      data-tip="${u(`Open advanced options: settings for experienced users`)}"
    >
      ${u(`Advanced`)}
    </button>
    <button
      id="optionsReset"
      style="flex: 1; min-width: max-content"
      data-tip="${u(`Click to restore default options and reload the page`)}"
    >
      ${u(`Reset`)}
    </button>
  </div>
`,Ss=new WeakMap;N(`optionsContent`).innerHTML=xs,N(`dialogs`).insertAdjacentHTML(`beforeend`,Go()),Cs(),Qs(),Zo(()=>Ts(`performancePreset`));function Cs(){for(let e of[N(`options`),N(No)])e.addEventListener(`input`,Ns),e.addEventListener(`change`,Ns);N(`interfaceLanguage`).addEventListener(`change`,e=>ec(e.target));let e=e=>{let t=e.target;t.id===`restoreDefaultMapSize`?Fs():t.id===`configureWorld`?L.WorldConfigurator.open():t.id===`setupLore`?L.LoreEditor.open():t.id===`optionsMapHistory`?pr():t.id===`optionsCopySeed`?oo():t.id===`templateInputContainer`?L.HeightmapSelection.open():t.id===`viewportFit`?Js():t.id===`zoomExtentDefault`?Ys():t.id===`translateExtent`?Zs(t):t.id===`openPerformanceSettings`?ds.open():t.id===`speakerTest`?$s():t.id===`themeColorRestore`?Us():t.id===`openAdvancedOptions`?qo.open():t.id===`optionsReset`&&Sn()};N(`optionsContent`).addEventListener(`click`,e),N(No).addEventListener(`click`,e)}function ws(e){return document.querySelectorAll(`:is(#options, #${No}) [data-option="${e}"]`)}function Z(e){let t=ws(e)[0];if(!t)throw Error(`Missing option control: ${e}`);return t}function Ts(e,t){let n=vs[e].read(options);if(n!==null)for(let r of ws(e))r!==t&&(r.value=String(n),Ss.delete(r))}function Es(){let e=ws(`template`)[0],t=options.generation.template;e&&t&&Wt(e,t,He[t]?.name||fs[t]?.name||t);for(let e of Object.keys(vs))Ts(e);Os(),ks(),As(),js(),Ds()}function Ds(){let e=!!options.map.viewOnly;document.body.classList.toggle(`view-only`,e),e&&M(`layersTab`)?.click();let t=M(`saveButton`);t&&(t.disabled=e,t.dataset.tip=u(e?`The map is in view-only mode and cannot be saved`:`Save fully-functional map file`))}function Os(){let e=N(`options`).querySelector(`[data-option-output="manors"]`);e&&(e.value=ce()?u(`Auto`):String(options.generation.burgs.limit))}function ks(){let{density:e}=options.generation.graph,t=fe(e),n=ws(`points`)[0];n&&(n.value=String(e),n.dataset.cells=String(t));let r=N(`options`).querySelector(`[data-option-output="points"]`);r&&(r.value=`${t/1e3}K`,r.style.color=Be(t))}function As(){let e=String(ae[options.generation.cultures.set]?.max??0);for(let t of ws(`cultures`))t.max=e,t.value=String(options.generation.cultures.limit)}function js(){let e=N(`options`).querySelector(`[data-option="pngResolution"]`);e&&(e.value=String(options.app.export.pngResolution))}function Ms(e){return Object.values(vs).find(t=>t.pin===e)?.read(options)??void 0}function Ns(e){let t=e.target,n=t.dataset.option;if(!n||!Object.hasOwn(vs,n))return;let r=vs[n];(r.event!==`change`||e.type===`change`)&&((e.type!==`change`||Ss.get(t)!==t.value)&&(r.update(t.value),Ts(n,t)),e.type===`input`?Ss.set(t,t.value):(Ss.delete(t),b.persist()))}function Ps(){let e=e=>{let t=Z(e),n=Math.max(+t.value||0,+t.min||1);return t.value=String(n),n},t=e(`mapWidth`),n=e(`mapHeight`);if(b.set(e=>{e.generation.graph.width=t,e.generation.graph.height=n}),v.set(`mapWidth`,t),v.set(`mapHeight`,n),options.generation.graph.width>window.innerWidth||options.generation.graph.height>window.innerHeight){let e=`${window.innerWidth} x ${window.innerHeight}`;I(u(`Map size is larger than the window ({{size}}). It can affect performance`,{size:e}),!1,`warn`,4e3)}}function Fs(){b.set(e=>{e.generation.graph.width=window.innerWidth,e.generation.graph.height=window.innerHeight}),v.clear(`mapWidth`),v.clear(`mapHeight`),Es()}function Is(e){let t=Po[e];t&&(b.set(e=>Object.assign(e.generation.graph,{sampling:t.sampling,jitter:t.jitter})),Ts(`sampling`),Ts(`jitter`))}function Ls(e){b.set(t=>t.generation.graph.density=e),ks()}function Rs(e){ie.setShape(e);let t=N(`emblemShapeImage`),{shieldPaths:n}=ft,r=n[e];r?t.setAttribute(`d`,r):t.removeAttribute(`d`);let i=[`culture`,`state`,`random`].includes(e)?null:e;if(e===`random`)for(let e of pack.cultures)e.removed||(e.shield=de.getRandomShield());for(let e of pack.states){if(!e.i||e.removed||!e.coa||`icon`in e.coa)continue;let t=i||ie.getShield(e.culture??0);t!==e.coa.shield&&(e.coa.shield=t,ft.trigger(`stateCOA${e.i}`,e.coa))}for(let e of pack.provinces){if(!e.i||e.removed||!e.coa||`icon`in e.coa)continue;let t=i||ie.getShield(pack.cells.culture[e.center]??0,e.state);t!==e.coa.shield&&(e.coa.shield=t,ft.trigger(`provinceCOA${e.i}`,e.coa))}for(let e of pack.burgs){if(!e.i||e.removed||!e.coa||`icon`in e.coa)continue;let t=i||ie.getShield(e.culture??0,e.state);t!==e.coa.shield&&(e.coa.shield=t,ft.trigger(`burgCOA${e.i}`,e.coa))}}function zs(e){if(Number.isNaN(e)||e<.5)return;let t=Math.min(e,Bs());Z(`uiSize`).value=String(t),document.body.style.fontSize=`${r(t*10,2)}px`,N(`options`).style.width=`${t*300}px`}var Bs=()=>r(Math.min(window.innerHeight/465,window.innerWidth/302),1);function Vs(e){N(`tooltip`).style.fontSize=`calc(${e}px + 0.5vw)`}function Hs(e,t){b.set(n=>{n.app.ui.themeColor=e,n.app.ui.transparency=t}),Gs(e,t)}function Us(){Hs(Ie,options.app.ui.transparency)}function Ws(e){let{s:t,l:n}=j(options.app.ui.themeColor);Hs(j(+e,t,n).hex(),options.app.ui.transparency)}function Gs(e,t){Z(`transparency`).value=String(t);let n=(100-t)/100,r=Math.min(n+.3,1),{h:i,s:a,l:o}=j(e);Z(`themeColor`).value=e,Z(`themeHue`).value=String(i);let s=[[`--bg-opacity`,String(n)],[`--bg-main`,j(i,a,o,n).toString()],[`--bg-lighter`,j(i,a,o+.02,n).toString()],[`--bg-light`,j(i,a-.02,o+.06,n).toString()],[`--light-solid`,j(i,a+.01,o+.05,1).toString()],[`--dark-solid`,j(i,a,o-.2,1).toString()],[`--header`,j(i,a,o-.03,r).toString()],[`--header-active`,j(i,a,o-.09,r).toString()],[`--bg-disabled`,j(i,a-.04,o+.09).toString()],[`--bg-dialogs`,j(0,0,.98,n).toString()]];for(let[e,t]of s)document.documentElement.style.setProperty(e,t)}function Ks(e){let n=Z(`zoomExtentMin`),r=Z(`zoomExtentMax`);+n.value>+r.value&&([n.value,r.value]=[r.value,n.value]),Xs(Math.max(+n.value,.01),Math.min(+r.value,200)),V(t(+e,.01,200))}function qs(){let e=+Z(`viewportWidth`).value,t=+Z(`viewportHeight`).value;e>0&&t>0&&(Mn(e,t),b.set(e=>e.app.viewport={width:vt.width,height:vt.height}))}function Js(){b.set(e=>e.app.viewport=null),Pn()}function Ys(){b.set(e=>e.app.zoomExtent.max=b.getDefaultOptions().app.zoomExtent.max),Z(`zoomExtentMax`).value=String(options.app.zoomExtent.max),Nn(),V(options.app.zoomExtent.min)}function Xs(e,t){b.set(n=>n.app.zoomExtent={min:e,max:t}),Z(`zoomExtentMin`).value=String(e),Z(`zoomExtentMax`).value=String(t),jn(e,t),On()}function Zs(e){let t=!+(e.dataset.on??0);e.dataset.on=String(+t);let{width:n,height:r}=options.map.graph;t?Tn(-n/2,-r/2,n*1.5,r*1.5):Tn(0,0,n,r)}function Qs(){let e=0,t=Z(`speakerVoice`),n=setInterval(()=>{let r=speechSynthesis.getVoices();if(r.length){clearInterval(n);for(let[e,n]of r.entries())t.options.add(new Option(n.name,String(e)));t.value=options.app.ui.speakerVoice||String(r.findIndex(e=>e.lang===`en-US`))}else{if(++e<10)return;clearInterval(n),t.options.length||t.options.add(new Option(u(`No voices available`),``))}},1e3)}function $s(){let e=new SpeechSynthesisUtterance(u(`The quick brown fox jumps over the lazy dog`)),t=speechSynthesis.getVoices();t.length&&(e.voice=t[Number(options.app.ui.speakerVoice)]??e.voice),speechSynthesis.speak(e)}function ec(e){let t=e.value;o(t)&&(b.set(e=>e.app.language=t),b.persist(),t!==d.language&&F.confirm({title:u(`Change language`),message:m(u(`The interface switches to {{language}} after a reload`,{language:f[t]}),u(`If you have unsaved changes, save the map first`)),confirm:u(`Reload`),cancel:u(`Not now`),onConfirm:()=>{window.onbeforeunload=null,location.reload()}}))}var tc=()=>t(r(window.innerWidth/1280,1),1,Bs());function nc(){let e=options.generation.template;if(e){let t=He[e]?.name||fs[e]?.name||e;Wt(Z(`template`),e,t)}gs(N(`options`),Ms),gs(N(No),Ms);let{ui:t,emblems:n}=options.app;ie.setShape(n.shape),Vs(t.tooltipSize),Z(`uiSize`).max=String(Bs()),zs(t.size??tc()),Gs(t.themeColor,t.transparency),ts(),Nn()}var rc={discord:C(`https://discordapp.com/invite/X7E84HU`,`Discord`),reddit:C(`https://www.reddit.com/r/FantasyMapGenerator`,`Reddit`),patreon:C(`https://www.patreon.com/azgaar`,`Patreon`)},ic={armoria:C(`https://azgaar.github.io/Armoria`,`Armoria`),deorum:C(`https://deorum.vercel.app`,`Deorum`)},ac=`https://github.com/Azgaar/Fantasy-Map-Generator/wiki`,oc={quickStart:C(`${ac}/Quick-Start-Tutorial`,u(`Quick start tutorial`)),qaa:C(`${ac}/Q&A`,u(`Q&A page`)),video:C(`https://youtube.com/playlist?list=PLtgiuDC8iVR2gIG8zMTRn7T_L0arl9h1C`,u(`Video tutorial`))},sc=[C(`https://github.com/Azgaar/Fantasy-Map-Generator`,u(`GitHub repository`)),C(`https://github.com/Azgaar/Fantasy-Map-Generator/blob/master/LICENSE`,u(`License`)),C(`${ac}/Changelog`,u(`Changelog`)),C(`${ac}/Hotkeys`,u(`Hotkeys`)),C(`https://trello.com/b/7x832DG4/fantasy-map-generator`,u(`Devboard`)),`<a href="mailto:azgaar.fmg@yandex.by" target="_blank">${u(`Contact Azgaar`)}</a>`];function cc(){return`${u(`Fantasy Map Generator (FMG) is a free open-source application. It means that you own all created maps and can use them as you wish.`)}

    <p>
      ${u(`The development is community-backed, you can donate on {{- patreon}}. You can also help creating overviews, tutorials and spreding the word about the Generator.`,{patreon:rc.patreon})}
    </p>

    <p>
      ${u(`The best way to get help is to contact the community on {{- discord}} and {{- reddit}}. Before asking questions, please check out the {{- quickStart}}, the {{- qaa}}, and {{- video}}.`,{...rc,...oc})}
    </p>

    <ul style="columns:2">${sc.map(e=>`<li>${e}</li>`).join(``)}</ul>

    <p>${u(`Check out our other projects`)}:
      <ul>
        <li>${u(`{{- armoria}}: a tool for creating heraldic coats of arms`,{armoria:ic.armoria})}</li>
        <li>${u(`{{- deorum}}: a vast gallery of customizable fantasy characters`,{deorum:ic.deorum})}</li>
      </ul>
    </p>`}function lc(){F.message({message:cc(),title:document.title,width:`28em`})}var uc=`
  <div id="exportMapData" style="display: none" class="dialog">
    <div style="margin-bottom: 0.3em; font-weight: bold">${u(`Download image`)}</div>
    <div>
      <button data-action="svg" data-tip="${u(`Download the map as vector image (open directly in browser or Inkscape)`)}">.svg</button>
      <button data-action="png" data-tip="${u(`Download visible part of the map as .png (lossless compressed)`)}">.png</button>
      <button data-action="jpeg" data-tip="${u(`Download visible part of the map as .jpeg (lossy compressed) image`)}">.jpeg</button>
      <button data-action="tiles" data-tip="${u(`Split map into smaller png tiles and download as zip archive`)}">${u(`tiles`)}</button>
      <span data-tip="${u(`Check to not allow system to automatically hide labels`)}">
        <input id="showLabels" class="checkbox" type="checkbox" />
        <label for="showLabels" class="checkbox-label">${u(`Show all labels`)}</label>
      </span>
    </div>
    <div
      data-tip="${u(`Define scale of a saved png/jpeg image (e.g. 5x). Saving big images is slow and may cause a browser crash!`)}"
      style="margin-bottom: 0.3em"
    >
      ${u(`PNG / JPEG scale`)}:
      <input id="pngResolutionInput" data-stored="pngResolution" type="range" min="1" max="8" value="1" style="width: 10em" />
      <input id="pngResolutionOutput" data-stored="pngResolution" type="number" min="1" max="8" value="1" />
    </div>
    <p>${u(`Generator uses pop-up window to download files. Please ensure your browser does not block popups.`)}</p>
    <div style="margin: 1em 0 0.3em; font-weight: bold">${u(`Export to GeoJSON`)}</div>
    <div>
      <button data-action="geojsonCells" data-tip="${u(`Export to GeoJSON`)}">${u(`Cells`)}</button>
      <button data-action="geojsonRoutes" data-tip="${u(`Export to GeoJSON`)}">${u(`Routes`)}</button>
      <button data-action="geojsonRivers" data-tip="${u(`Export to GeoJSON`)}">${u(`Rivers`)}</button>
      <button data-action="geojsonMarkers" data-tip="${u(`Export to GeoJSON`)}">${u(`Markers`)}</button>
      <button data-action="geojsonZones" data-tip="${u(`Export to GeoJSON`)}">${u(`Zones`)}</button>
    </div>
    <p>
      ${m(u(`GeoJSON format is used in GIS tools such as QGIS.`),u(`Check out {{- wiki}} for guidance.`,{wiki:C(`https://github.com/Azgaar/Fantasy-Map-Generator/wiki/GIS-data-export`,u(`wiki`))}))}
    </p>
    <div style="margin: 1em 0 0.3em; font-weight: bold">${u(`Export to JSON`)}</div>
    <div>
      <button data-action="jsonFull" data-tip="${u(`Download full data in JSON`)}">${u(`Full`)}</button>
      <button data-action="jsonMinimal" data-tip="${u(`Download minimal data in JSON`)}">${u(`Minimal`)}</button>
      <button data-action="jsonPackCells" data-tip="${u(`Download map metadata and pack cells data in JSON`)}">${u(`Pack cells`)}</button>
      <button data-action="jsonGridCells" data-tip="${u(`Download map metadata and grid cells data in JSON`)}">${u(`Grid cells`)}</button>
    </div>
    <p>${u(`Export in JSON format can be used as an API replacement.`)}</p>
  </div>

  <div id="saveMapData" style="display: none" class="dialog">
    <div style="margin-top: 0.3em">
      <strong>${u(`Save map to`)}</strong>
      <button
        data-action="saveToMachine"
        data-tip="${u(`Save to a new file; Shift-click to overwrite the last saved file`)}"
        data-shortcut="Ctrl + S"
        style="font-weight: 600"
      >
        ${u(`machine`)}
      </button>
      <button id="saveToDropboxButton" data-action="saveToDropbox" data-tip="${u(`Save Map to Dropbox`)}" data-shortcut="Ctrl + C">
        dropbox
      </button>
      <button id="saveToStorageButton" data-action="saveToStorage" data-tip="${u(`Save the project to browser storage only`)}" data-shortcut="F6">${u(`browser`)}</button>
    </div>
    <p>
      ${u(`Each save creates a new file, so earlier saves stay as backups. Where your browser supports it, Shift-click machine or press Ctrl + Shift + S to overwrite the last saved file.`)}
    </p>
    <p>
      ${u(`Maps are saved in .map format, that can be loaded back via the Load in menu. There is no way to restore the progress if file is lost. Please keep old save files on your machine or cloud storage as backups.`)}
    </p>
    <div data-tip="${u(`Saved map opens for browsing only, with editing disabled. Not a protection: the file itself can still be changed`)}">
      <input id="saveViewOnly" class="checkbox" type="checkbox" />
      <label for="saveViewOnly" class="checkbox-label">${u(`View-only mode`)}</label>
    </div>
  </div>

  <div id="loadMapData" style="display: none" class="dialog">
    <div>
      <strong>${u(`Load map from`)}</strong>
      <button id="loadMapFromMachine" data-tip="${u(`Load map file (.map or .gz) from your local disk`)}">${u(`machine`)}</button>
      <button data-action="loadFromURL" data-tip="${u(`Load map file (.map or .gz) file from URL. Note that the server should allow CORS`)}">
        URL
      </button>
      <button data-action="loadFromStorage" data-tip="${u(`Load map from browser storage (if saved before)`)}">${u(`storage`)}</button>
    </div>
    <p>${u(`Click on storage to open the last saved map.`)}</p>
    <div id="loadFromDropbox">
      <p style="margin-bottom: 0.3em">
        ${u(`Or load from your Dropbox account`)}
        <button id="dropboxConnectButton" data-action="connectDropbox" data-tip="${u(`Connect your Dropbox account to be able to load maps from it`)}">
          ${u(`Connect`)}
        </button>
      </p>
      <select id="loadFromDropboxSelect" style="width: 22em"></select>
      <div id="loadFromDropboxButtons" style="margin-bottom: 0.6em">
        <button data-action="loadFromDropbox" data-tip="${u(`Load map file (.map or .gz) from your Dropbox`)}">${u(`Load`)}</button>
        <button data-action="shareDropboxLink" data-tip="${u(`Select file and create a link to share with your friends`)}">${u(`Share`)}</button>
      </div>
      <div style="margin-top: 0.3em">
        <div id="sharableLinkContainer" style="display: none">
          <a id="sharableLink" target="_blank"></a>
          <i data-action="copyLink" data-tip="${u(`Copy link to the clipboard`)}" class="icon-clone pointer"></i>
        </div>
      </div>
    </div>
  </div>

  <div id="exportToPngTilesScreen" style="display: none" class="dialog">
    <p>${u(`Map will be split into tiles and downloaded as a single zip file. Avoid saving too large images`)}</p>
    <div data-tip="${u(`Number of columns`)}" style="margin-bottom: 0.3em">
      <div class="label">${u(`Columns`)}:</div>
      <input id="tileColsInput" data-stored="tileCols" type="range" min="2" max="26" value="8" style="width: 10em" />
      <input id="tileColsOutput" data-stored="tileCols" type="number" min="2" value="8" />
    </div>
    <div data-tip="${u(`Number of rows`)}" style="margin-bottom: 0.3em">
      <div class="label">${u(`Rows`)}:</div>
      <input id="tileRowsInput" data-stored="tileRows" type="range" min="2" max="26" value="8" style="width: 10em" />
      <input id="tileRowsOutput" data-stored="tileRows" type="number" min="2" value="8" />
    </div>
    <div data-tip="${u(`Image scale relative to image size (e.g. 5x)`)}" style="margin-bottom: 0.3em">
      <div class="label">${u(`Scale`)}:</div>
      <input id="tileScaleInput" data-stored="tileScale" type="range" min="1" max="4" value="1" style="width: 10em" />
      <input id="tileScaleOutput" data-stored="tileScale" type="number" min="1" value="1" />
    </div>
    <div data-tip="${u(`Calculated size of image if combined`)}" style="margin-bottom: 0.3em">
      <div class="label">${u(`Total size`)}:</div>
      <div id="tileSize" style="display: inline-block">1000 x 1000 px</div>
    </div>
    <div id="tileStatus" style="font-style: italic"></div>
  </div>
`,dc={svg:()=>B.ExportMap.exportToSvg(),png:()=>B.ExportMap.exportToPng(),jpeg:()=>B.ExportMap.exportToJpeg(),tiles:()=>Sc(),geojsonCells:()=>B.ExportMap.saveGeoJsonCells(),geojsonRoutes:()=>B.ExportMap.saveGeoJsonRoutes(),geojsonRivers:()=>B.ExportMap.saveGeoJsonRivers(),geojsonMarkers:()=>B.ExportMap.saveGeoJsonMarkers(),geojsonZones:()=>B.ExportMap.saveGeoJsonZones(),jsonFull:()=>B.ExportJson.exportToJson(`Full`),jsonMinimal:()=>B.ExportJson.exportToJson(`Minimal`),jsonPackCells:()=>B.ExportJson.exportToJson(`PackCells`),jsonGridCells:()=>B.ExportJson.exportToJson(`GridCells`),saveToMachine:e=>B.Save.toMachine(e.shiftKey,fc()),saveToDropbox:()=>B.Save.toDropbox(fc()),saveToStorage:()=>B.Save.toStorage(),loadFromURL:()=>xc(),loadFromStorage:()=>B.Load.quickLoad(),connectDropbox:()=>vc(),loadFromDropbox:()=>B.Load.loadFromDropbox(),shareDropboxLink:()=>B.Load.createSharableDropboxLink(),copyLink:()=>yc()},fc=()=>N(`saveViewOnly`).checked;function pc(){N(`saveToStorageButton`).disabled=fc()}var mc=e=>[{label:u(`Close`),onClick:()=>F.close(e)}];function hc(){N(`saveViewOnly`).checked=!1,pc(),F.open(`saveMapData`,{title:u(`Save map`),width:`25em`,position:{my:`center`,at:`center`,of:`svg`},buttons:mc(`saveMapData`),persistent:!0})}function gc(){N(`showLabels`).checked=options.app.labels.showAll,F.open(`exportMapData`,{title:u(`Export map data`),width:`26em`,position:{my:`center`,at:`center`,of:`svg`},buttons:mc(`exportMapData`),persistent:!0})}async function _c(){if(F.open(`loadMapData`,{title:u(`Load Map`),width:`auto`,position:{my:`center`,at:`center`,of:`svg`},buttons:mc(`loadMapData`),persistent:!0}),!M(`loadFromDropbox`))return;N(`sharableLinkContainer`).style.display=`none`;let e=N(`dropboxConnectButton`),t=N(`loadFromDropboxButtons`),n=N(`loadFromDropboxSelect`);if(!await B.Cloud.isConnected()){e.style.display=`inline-block`,t.style.display=`none`,n.style.display=`none`;return}e.style.display=`none`,n.style.display=`block`,n.innerHTML=`<option value="" disabled selected>${u(`Loading`)}…</option>`;let i=await B.Cloud.list();if(!i.length)t.style.display=`none`,n.innerHTML=`<option value="" disabled selected>${u(`Save files to Dropbox first`)}</option>`;else{t.style.display=`block`,n.innerHTML=``;for(let{name:e,updated:t,size:a,path:o}of i){let i=`${new Date(t).toLocaleDateString()}: ${e} [${r(a/1024/1024,2)} MB]`;n.options.add(new Option(i,o))}}}async function vc(){await B.Cloud.connect(),await B.Cloud.isConnected()&&_c()}function yc(){let e=N(`sharableLink`).getAttribute(`href`)??``;navigator.clipboard.writeText(e).then(()=>I(u(`Link is copied to the clipboard`),!0,`success`,8e3))}var bc=/(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-/]))?/;function xc(){F.message({message:`${u(`Provide URL to map file`)}:
    <input id="mapURL" type="url" style="width: 24em" placeholder="https://e-cloud.com/test.map" />
    <br /><i>${u(`Please note server should allow CORS for file to be loaded. If CORS is not allowed, save file to Dropbox and provide a direct link`)}</i>`,title:u(`Load Map from URL`),width:`27em`,buttons:[{label:u(`Load`),onClick:()=>{let e=N(`mapURL`).value;if(!bc.test(e))return I(u(`Please provide a valid URL`),!1,`error`),!1;B.Load.loadMapFromURL(e)}},{label:u(`Cancel`)}]})}function Sc(){N(`tileStatus`).innerHTML=``,F.closeAll(),Dc();let e=Array.from(N(`exportToPngTilesScreen`).querySelectorAll(`input`));for(let t of e)t.addEventListener(`input`,Cc);F.open(`exportToPngTilesScreen`,{title:u(`Download tiles`),width:`23em`,buttons:[{label:u(`Download`),onClick:()=>B.ExportMap.exportToPngTiles()},{label:u(`Cancel`),onClick:()=>{F.close(`exportToPngTilesScreen`)}}],onClose:()=>{for(let t of e)t.removeEventListener(`input`,Cc);P(`#debug`).selectAll(`*`).remove()},persistent:!0})}function Cc(){let{nextElementSibling:e,previousElementSibling:t}=this;e instanceof HTMLInputElement&&(e.value=this.value),t instanceof HTMLInputElement&&(t.value=this.value),wc(this),Dc()}function wc(e){let t=+e.value;t>0&&b.set(n=>{let{tiles:r}=n.app.export;e.dataset.stored===`pngResolution`?n.app.export.pngResolution=t:e.dataset.stored===`tileCols`?r.cols=t:e.dataset.stored===`tileRows`?r.rows=t:e.dataset.stored===`tileScale`&&(r.scale=t)})}var Tc=`ABCDEFGHIJKLMNOPQRSTUVWXYZ`,Ec=e=>(e>=26?Tc[Math.floor(e/26)-1]:``)+Tc[e%26];function Dc(){let{cols:e,rows:t,scale:n}=options.app.export.tiles,r=options.map.graph.width*n*e,i=options.map.graph.height*n*t,a=r*i,o=N(`tileSize`);o.innerHTML=`${r} x ${i} px`,o.style.color=a>1e9?`#d00b0b`:a>1e8?`#9e6409`:`#1a941a`;let s=options.map.graph.width/e|0,c=options.map.graph.height/t|0,l=[],u=[];for(let e=0,t=0;e+c<=options.map.graph.height;e+=c,t++)for(let n=0,r=1;n+s<=options.map.graph.width;n+=s,r++){l.push(`<rect x=${n} y=${e} width=${s} height=${c} />`);let i=`${Ec(t)}${r}`;u.push(`<text x=${n+s/2} y=${e+c/2}>${i}</text>`)}P(`#debug`).html(`<g fill="none" stroke="#000">${l.join(``)}</g>
    <g fill="#000" stroke="none" text-anchor="middle" dominant-baseline="central" font-size="18px">${u.join(``)}</g>`)}var Oc=kt(`.map,.gz`);Oc.id=`mapToLoad`,Oc.onchange=()=>{let e=Oc.files?.[0];Oc.value=``,F.closeAll(),e&&B.Load.uploadMap(e)};function kc(){Oc.click()}function Ac(){N(`dialogs`).insertAdjacentHTML(`afterbegin`,uc);for(let e of[`exportMapData`,`saveMapData`,`loadMapData`])N(e).addEventListener(`click`,e=>{let t=e.target.closest(`[data-action]`)?.dataset.action;t&&dc[t]?.(e)});for(let e of document.querySelectorAll(`[data-stored="pngResolution"]`))e.addEventListener(`input`,()=>{for(let t of document.querySelectorAll(`[data-stored="pngResolution"]`))t.value=e.value;wc(e)});N(`showLabels`).addEventListener(`change`,function(){b.set(e=>e.app.labels.showAll=this.checked),w.draw(`labels`)}),N(`saveViewOnly`).addEventListener(`change`,pc),N(`loadMapFromMachine`).addEventListener(`click`,kc)}Ac();var jc=`input, textarea, button, select, option`,Mc=(e,t)=>{let n=e.target;return n.closest(jc)?null:n.closest(t)};function Nc(e,n){getComputedStyle(e).position===`static`&&(e.style.position=`relative`),e.addEventListener(`mousedown`,e=>{Mc(e,n)&&e.preventDefault()}),e.addEventListener(`pointerdown`,r=>{let i=Mc(r,n);if(r.button!==0||!i)return;let a=i.getBoundingClientRect(),o=getComputedStyle(e),s={left:parseFloat(o.left)||0,top:parseFloat(o.top)||0};Jt(r,(n,r)=>{let i=s.left+t(n,-a.left,window.innerWidth-a.right),o=s.top+t(r,-a.top,window.innerHeight-a.bottom);Object.assign(e.style,{left:`${i}px`,top:`${o}px`,right:`auto`,bottom:`auto`})})})}function Pc(e){let t=e.target;t.tagName===`BUTTON`&&(!t.classList.contains(`pressed`)&&t.id!==`viewStandard`?L.View3d.open(t.id):L.View3d.enterStandard())}var Fc={layersTab:`layersContent`,styleTab:`styleContent`,optionsTab:`optionsContent`,toolsTab:`toolsContent`,aboutTab:`aboutContent`};function Ic(e){localStorage.getItem(`fmg-disable-click-arrow-tooltip`)||($t(),localStorage.setItem(bn,`true`),N(`optionsTrigger`).classList.remove(`glow`)),N(`regenerate`).style.display=`none`,N(`options`).style.display=`block`,N(`optionsTrigger`).style.display=`none`,e?.stopPropagation()}function Lc(e){N(`options`).style.display=`none`,N(`optionsTrigger`).style.display=`block`,e?.stopPropagation()}function Rc(e){N(`options`).style.display===`none`?Ic(e):Lc(e)}function zc(e){Ic(),Bc(e)}function Bc(e){let t=N(`options`).querySelector(`.tab > button.active`);if(t?.id===e)return;t?.id===`styleTab`&&L.StyleEditor.close(),t?.classList.remove(`active`),N(e).classList.add(`active`);for(let e of N(`options`).querySelectorAll(`.tabcontent`))e.style.display=`none`;let n=e===`toolsTab`&&options.app.mode===`heightmap`?`heightmapMenu`:Fc[e];n&&(N(n).style.display=`block`),e===`styleTab`&&L.StyleEditor.open()}function Vc(e){let t=e.target;if(t.closest(`[data-option]`))return;let{id:n,value:r}=t;if(n.endsWith(`Input`)){let e=M(`${n.slice(0,-5)}Output`);e&&(e.value=r)}else if(n.endsWith(`Output`)){let e=M(`${n.slice(0,-6)}Input`);e&&(e.value=r)}}function Hc(){Nc(N(`optionsContainer`),`.drag-trigger`),Nc(N(`heightmapFinalize`),`div`),localStorage.getItem(`fmg-disable-click-arrow-tooltip`)&&($t(),N(`optionsTrigger`).classList.remove(`glow`));let e=N(`optionsTrigger`);e.addEventListener(`mouseenter`,()=>{e.classList.contains(`glow`)||N(`options`).style.display===`none`&&(N(`regenerate`).style.display=`block`)}),N(`collapsible`).addEventListener(`mouseleave`,()=>{N(`regenerate`).style.display=`none`}),N(`options`).querySelector(`div.tab`)?.addEventListener(`click`,e=>{let t=e.target;t.tagName===`BUTTON`&&Bc(t.id)});for(let e of[`options`,`dialogs`])N(e).addEventListener(`input`,Vc);N(`sticked`).addEventListener(`click`,e=>{let t=e.target.id;t===`newMapButton`?Mo():t===`saveButton`?hc():t===`exportButton`?gc():t===`loadButton`?_c():t===`zoomReset`?kn(1e3):t===`searchButton`&&L.Omnibar.open()}),N(`viewMode`).addEventListener(`click`,Pc),N(`optionsTrigger`).addEventListener(`click`,Ic),N(`regenerate`).addEventListener(`click`,()=>Mo()),N(`optionsHide`).addEventListener(`click`,Lc)}Hc();var Uc={political:[`borders`,`burgIcons`,`ice`,`labels`,`lakes`,`rivers`,`routes`,`scaleBar`,`states`,`vignette`],cultural:[`borders`,`burgIcons`,`cultures`,`labels`,`lakes`,`rivers`,`routes`,`scaleBar`,`vignette`],religions:[`borders`,`burgIcons`,`labels`,`lakes`,`religions`,`rivers`,`routes`,`scaleBar`,`vignette`],provinces:[`borders`,`burgIcons`,`labels`,`lakes`,`provinces`,`rivers`,`scaleBar`,`vignette`],biomes:[`biomes`,`ice`,`lakes`,`rivers`,`scaleBar`,`vignette`],heightmap:[`heightmap`,`lakes`,`rivers`,`vignette`],physical:[`coordinates`,`heightmap`,`ice`,`lakes`,`rivers`,`scaleBar`,`vignette`],poi:[`borders`,`burgIcons`,`heightmap`,`ice`,`lakes`,`markers`,`rivers`,`routes`,`scaleBar`,`vignette`],goods:[`borders`,`burgIcons`,`cells`,`goods`,`lakes`,`markets`,`rivers`,`routes`,`scaleBar`,`trade`,`vignette`],trade:[`borders`,`burgIcons`,`lakes`,`rivers`,`routes`,`scaleBar`,`states`,`trade`,`vignette`],military:[`borders`,`burgIcons`,`labels`,`lakes`,`military`,`rivers`,`routes`,`scaleBar`,`states`,`vignette`],emblems:[`borders`,`burgIcons`,`emblems`,`ice`,`lakes`,`rivers`,`routes`,`scaleBar`,`states`,`vignette`],landmass:[`scaleBar`]},Q={...Uc};Wc();function Wc(){let e=JSON.parse(localStorage.getItem(`presets`)||`null`);if(e)for(let t in e)e[t].every(e=>w.has(e))&&(Q[t]=e[t],Uc[t]||N(`layersPreset`).add(new Option(t,t)))}function Gc(){let e=localStorage.getItem(`preset`)||N(`layersPreset`).value,t=e in Q?e:`political`;Jc(t),w.restore({order:w.state.order,active:Q[t]})}function Kc(e){let t=e.get(`layers`);if(t){let e=t.split(`,`).map(e=>e.trim()).filter(e=>w.has(e));e.length?w.set(e):h.error(`URL param layers="${t}" has no valid layer ids`);return}let n=e.get(`preset`),r=n&&qc(n);r?(Jc(r),w.set(Q[r])):n&&h.error(`URL param preset="${n}" is invalid`)}function qc(e){let t=e.toLowerCase().trim(),n=Object.keys(Q).find(e=>e.toLowerCase()===t);if(n)return n;let r=Array.from(N(`layersPreset`).options).find(e=>e.text.toLowerCase()===t);return r?.value&&r.value in Q?r.value:void 0}function Jc(e){N(`layersPreset`).value=e,localStorage.setItem(`preset`,e),N(`removePresetButton`).style.display=Uc[e]?`none`:`inline-block`,N(`savePresetButton`).style.display=`none`}function Yc(e){e in Q&&(Jc(e),w.set(Q[e]))}function Xc(){F.confirm({title:u(`Save Layers Preset`),message:`<label>${u(`Preset name`)}: <input id="layersPresetName" type="text" autocomplete="off" /></label>`,confirm:u(`Save`),onConfirm:()=>{let e=N(`layersPresetName`).value.trim();e&&(Q[e]=w.all.filter(e=>Jn.has(e.id)&&w.isOn(e.id)).map(e=>e.id),N(`layersPreset`).add(new Option(e,e,!1,!0)),localStorage.setItem(`presets`,JSON.stringify(Q)),localStorage.setItem(`preset`,e),N(`removePresetButton`).style.display=`inline-block`,N(`savePresetButton`).style.display=`none`)}}),N(`layersPresetName`).focus()}function Zc(){let e=N(`layersPreset`).value;delete Q[e],N(`layersPreset`).options.remove(Array.from(N(`layersPreset`).options).findIndex(t=>t.value===e)),N(`layersPreset`).value=`custom`,N(`removePresetButton`).style.display=`none`,N(`savePresetButton`).style.display=`inline-block`,localStorage.setItem(`presets`,JSON.stringify(Q)),localStorage.removeItem(`preset`)}function Qc(){let e=e=>[...e].sort().join(`,`),t=e(w.all.filter(e=>Jn.has(e.id)&&w.isOn(e.id)).map(e=>e.id)),n=Object.keys(Q).find(n=>e(Q[n])===t);N(`layersPreset`).value=n??`custom`,N(`removePresetButton`).style.display=n&&!Uc[n]?`inline-block`:`none`,N(`savePresetButton`).style.display=n?`none`:`inline-block`}N(`layersPreset`).addEventListener(`change`,e=>{Yc(e.target.value)}),N(`savePresetButton`).addEventListener(`click`,Xc),N(`removePresetButton`).addEventListener(`click`,Zc),w.subscribe(Qc);function $c(e,t){return`<button id="${e}" data-tip="${t}" class="icon-book"></button>`}function el(e){return`<span data-col="note" data-tip="${e}" class="icon-book pointer"></span>`}var tl=[`culturesEditorRefresh`,`biomesEditorRefresh`,`diplomacyOverviewRefresh`,`provincesEditorRefresh`,`religionsEditorRefresh`,`statesEditorRefresh`,`zonesEditorRefresh`,`goodsEditorRefresh`,`marketsOverviewRefresh`,`marketOverviewRefresh`,`marketDealsRefresh`,`burgsOverviewRefresh`,`routesOverviewRefresh`,`riversOverviewRefresh`,`featuresOverviewRefresh`,`militaryOverviewRefresh`,`regimentsOverviewRefresh`,`markersOverviewRefresh`,`journeysOverviewRefresh`];function nl(){for(let e of tl)M(e)?.click()}var rl=e=>e.link===!0,il=[{id:`assistant`,name:u(`Azgaar Assistant`),aliases:`help chat question ask faq support how why what ?`,matches:al,run:(e,t)=>t&&al(t)?L.Assistant.ask(t):L.Assistant.open()},{id:`startTour`,name:u(`Start Interactive Tour`),aliases:`help guide tutorial`,run:()=>B.UiTour.start()},{id:`newMap`,name:u(`Generate New Map`),aliases:`regenerate random create`,run:()=>Mo()},{id:`saveToMachine`,name:u(`Save Map File`),aliases:`save .map disk`,run:()=>B.Save.toMachine()},{id:`overwriteMapFile`,name:u(`Overwrite Saved Map File`),aliases:`save same file update replace .map`,run:()=>B.Save.toMachine(!0)},{id:`loadFromFile`,name:u(`Load Map from File`),aliases:`open upload disk`,run:()=>kc()},{id:`quickLoad`,name:u(`Quick Load Map`),aliases:`browser storage restore`,run:()=>B.Load.quickLoad()},{id:`saveToStorage`,name:u(`Save Map to browser storage`),aliases:`browser storage`,run:()=>B.Save.toStorage()},{id:`saveToDropbox`,name:u(`Save Map to Dropbox`),aliases:`cloud`,run:()=>B.Save.toDropbox()},{id:`loadFromURL`,name:u(`Load Map from URL`),aliases:`open link`,run:()=>xc()},{id:`saveButton`,name:u(`Show Save Panel`),link:!0,aliases:`store dialog`,run:()=>hc()},{id:`loadButton`,name:u(`Load Map`),aliases:`open dialog`,run:()=>_c()},{id:`exportButton`,name:u(`Show Export Panel`),link:!0,aliases:`map download image data`,run:()=>gc()},{id:`copyMapURL`,name:u(`Copy Map URL`),aliases:`seed link share clipboard`,run:()=>oo()},{id:`seedHistory`,name:u(`Show Seed History`),link:!0,aliases:`previous maps restore`,run:()=>pr()},{id:`editStatesButton`,name:u(`States Editor`),link:!0,aliases:`countries kingdoms nations`,run:()=>L.StatesEditor.open()},{id:`overviewBurgsButton`,name:u(`Burgs Overview`),link:!0,aliases:`settlements cities towns villages`,run:()=>L.BurgsOverview.open()},{id:`editCulturesButton`,name:u(`Cultures Editor`),link:!0,aliases:`people`,run:()=>L.CulturesEditor.open()},{id:`editReligions`,name:u(`Religions Editor`),link:!0,aliases:`faith beliefs`,run:()=>L.ReligionsEditor.open()},{id:`editProvincesButton`,name:u(`Provinces Editor`),link:!0,aliases:`territories counties`,run:()=>L.ProvincesEditor.open()},{id:`editHeightmapButton`,name:u(`Edit Heightmap`),link:!0,aliases:`terrain elevation`,run:()=>L.HeightmapEditor.open()},{id:`editBiomesButton`,name:u(`Biomes Editor`),link:!0,aliases:`environment terrain`,run:()=>L.BiomesEditor.open()},{id:`editReliefRules`,name:u(`Relief Rules`),link:!0,aliases:`terrain icons mountains hills trees biome rules`,run:()=>L.ReliefRulesEditor.open()},{id:`editDiplomacyButton`,name:u(`Diplomacy Overview`),link:!0,aliases:`relations allies wars`,run:()=>L.DiplomacyOverview.open()},{id:`overviewFeaturesButton`,name:u(`Geographical Features Overview`),link:!0,aliases:`islands lakes oceans landmasses water bodies continents`,run:()=>L.FeaturesOverview.open()},{id:`overviewRiversButton`,name:u(`Rivers Overview`),link:!0,aliases:`waterways`,run:()=>L.RiversOverview.open()},{id:`overviewRoutesButton`,name:u(`Routes Overview`),link:!0,aliases:`roads paths trails`,run:()=>L.RoutesOverview.open()},{id:`overviewMarkersButton`,name:u(`Markers Overview`),link:!0,aliases:`points of interest`,run:()=>L.MarkersOverview.open()},{id:`overviewLabelsButton`,name:u(`Labels Overview`),link:!0,aliases:`text typography`,run:()=>L.LabelsOverview.open()},{id:`editZonesButton`,name:u(`Zones Editor`),link:!0,aliases:`areas regions`,run:()=>L.ZonesEditor.open()},{id:`overviewMilitaryButton`,name:u(`Military Overview`),link:!0,aliases:`armies regiments`,run:()=>L.MilitaryOverview.open()},{id:`regiments`,name:u(`Regiments Overview`),link:!0,aliases:`military armies`,run:()=>L.RegimentsOverview.open()},{id:`editEmblemButton`,name:u(`Edit Emblem`),link:!0,aliases:`heraldry coat of arms`,run:()=>L.EmblemsEditor.openDefault()},{id:`editNotesButton`,name:u(`Notes Editor`),link:!0,aliases:`lore descriptions legends`,run:()=>L.NotesEditor.open()},{id:`lore`,name:u(`Setup Lore`),link:!0,aliases:`description history story`,run:()=>L.LoreEditor.open()},{id:`editNamesBaseButton`,name:u(`Namesbase Editor`),link:!0,aliases:`names language`,run:()=>L.NamesbaseEditor.open()},{id:`editUnitsButton`,name:u(`Units Editor`),link:!0,aliases:`scale distance population`,run:()=>L.UnitsEditor.open()},{id:`editCoastlineSettings`,name:u(`Coastline Settings`),link:!0,aliases:`coast islands oceans`,run:()=>L.CoastlineEditor.open()},{id:`editMeasurersButton`,name:u(`Measurers Editor`),link:!0,aliases:`rulers distances`,run:()=>L.MeasurersEditor.open()},{id:`editGoods`,name:u(`Goods Editor`),link:!0,aliases:`resources products economy`,run:()=>L.GoodsEditor.open()},{id:`overviewMarketsButton`,name:u(`Markets Overview`),link:!0,aliases:`economy trade`,run:()=>L.MarketsOverview.open()},{id:`productionChains`,name:u(`Production Chains`),link:!0,aliases:`goods recipes economy`,run:()=>L.ProductionChains.open()},{id:`editTradeAnimationButton`,name:u(`Trade Animation Editor`),link:!0,aliases:`economy`,run:()=>L.TradeAnimationEditor.open()},{id:`overviewJourneysButton`,name:u(`Journeys Overview`),link:!0,aliases:`travel quests`,run:()=>L.JourneysOverview.open()},{id:`transports`,name:u(`Transport Types`),link:!0,aliases:`journeys travel speed`,run:()=>L.TransportEditor.open()},{id:`burgGroups`,name:u(`Configure burg groups`),link:!0,aliases:`settlements cities towns villages types`,run:()=>L.BurgGroupEditor.open()},{id:`labelGroups`,name:u(`Configure Label Groups`),link:!0,aliases:`labels text typography fonts`,run:()=>L.LabelGroupsConfigurator.open()},{id:`routeGroups`,name:u(`Edit route groups`),link:!0,aliases:`roads paths trails types`,run:()=>L.RouteGroupsEditor.open()},{id:`world`,name:u(`World Configurator`),link:!0,aliases:`climate size latitude temperature`,run:()=>L.WorldConfigurator.open()},{id:`overviewCellsButton`,name:u(`Cell Details`),link:!0,aliases:`cell information`,run:()=>L.CellInfo.open()},{id:`overviewChartsButton`,name:u(`Data Charts`),link:!0,aliases:`statistics graphs`,run:()=>L.ChartsOverview.open()},{id:`addBurgTool`,name:u(`Add Burg`),aliases:`add burgs settlement city town village`,run:()=>L.BurgCreator.toggle()},{id:`addLabel`,name:u(`Add Label`),aliases:`text`,run:()=>L.LabelCreator.toggle()},{id:`addMarker`,name:u(`Add Marker`),aliases:`point of interest`,run:()=>L.MarkerCreator.toggle()},{id:`addRiver`,name:u(`Add River`),aliases:`waterway`,run:()=>L.RiverAutoCreator.toggle()},{id:`drawRiver`,name:u(`Draw River`),aliases:`add waterway manually`,run:()=>L.RiverCreator.open()},{id:`addRoute`,name:u(`Add Route`),aliases:`road trail path`,run:()=>L.RouteCreator.open()},{id:`selectHeightmap`,name:u(`Select Heightmap Template`),aliases:`precreated generation options`,run:()=>L.HeightmapSelection.open()},{id:`openSubmapTool`,name:u(`Create Submap`),aliases:`generate region`,run:()=>L.SubmapTool.open()},{id:`openTransformTool`,name:u(`Transform Map`),aliases:`rotate resize`,run:()=>L.TransformTool.open()},{id:`openWrapTool`,name:u(`Wrap Tool`),link:!0,aliases:`reshape cells brush`,run:()=>L.WrapTool.open()},{id:`openMinimapButton`,name:u(`Minimap`),link:!0,aliases:`navigation`,run:()=>L.Minimap.open()},{id:`viewMesh`,name:u(`3D Preview`),link:!0,aliases:`view mode mesh`,run:()=>L.View3d.open(`viewMesh`)},{id:`viewGlobe`,name:u(`Open Globe View`),link:!0,aliases:`view mode planet`,run:()=>L.View3d.open(`viewGlobe`)},{id:`showStatesChart`,name:u(`States bubble chart`),link:!0,aliases:`countries kingdoms area population bubble`,run:()=>L.StatesEditor.showChart()},{id:`showProvincesChart`,name:u(`Provinces chart`),link:!0,aliases:`territories area population treemap`,run:()=>L.ProvincesEditor.showChart()},{id:`showBurgsChart`,name:u(`Burgs bubble chart`),link:!0,aliases:`settlements cities population bubble`,run:()=>L.BurgsOverview.showChart()},{id:`showCulturesHierarchy`,name:u(`Cultures tree`),link:!0,aliases:`people origins tree`,run:()=>L.CulturesEditor.showHierarchy()},{id:`showReligionsHierarchy`,name:u(`Religions tree`),link:!0,aliases:`faith beliefs origins tree`,run:()=>L.ReligionsEditor.showHierarchy()},{id:`showRelationsHistory`,name:u(`Relations history`),link:!0,aliases:`diplomacy chronicle wars`,run:()=>L.DiplomacyOverview.showHistory()},{id:`regenerateStates`,name:`${u(`Regenerate`)}: ${u(`States`)}`,aliases:`generate countries kingdoms`,run:()=>$(dl)},{id:`regenerateProvinces`,name:`${u(`Regenerate`)}: ${u(`Provinces`)}`,link:!0,aliases:`generate counties`,run:()=>L.ProvincesRegeneration.open()},{id:`regenerateBurgs`,name:`${u(`Regenerate`)}: ${u(`Burgs`)}`,aliases:`generate settlements cities towns`,run:()=>$(fl)},{id:`regenerateCultures`,name:`${u(`Regenerate`)}: ${u(`Cultures`)}`,aliases:`generate people`,run:()=>$(yl)},{id:`regenerateReligions`,name:`${u(`Regenerate`)}: ${u(`Religions`)}`,aliases:`generate faith`,run:()=>$(vl)},{id:`regenerateRivers`,name:`${u(`Regenerate`)}: ${u(`Rivers`)}`,aliases:`generate waterways`,run:()=>$(ll)},{id:`regenerateRoutes`,name:`${u(`Regenerate`)}: ${u(`Routes`)}`,aliases:`generate roads`,run:()=>$(cl)},{id:`regenerateStateLabels`,name:`${u(`Regenerate`)}: ${u(`State Labels`)}`,aliases:`generate text placement`,run:()=>$(ol)},{id:`regenerateReliefIcons`,name:`${u(`Regenerate`)}: ${u(`Relief`)}`,aliases:`generate mountains forests`,run:()=>$(sl)},{id:`regenerateEmblems`,name:`${u(`Regenerate`)}: ${u(`Emblems`)}`,aliases:`generate heraldry`,run:()=>$(_l)},{id:`regenerateMarkers`,name:`${u(`Regenerate`)}: ${u(`Markers`)}`,link:!0,aliases:`generate points of interest settings configure multiplier`,run:()=>L.MarkersSettings.open()},{id:`regenerateZones`,name:`${u(`Regenerate`)}: ${u(`Zones`)}`,aliases:`generate regions`,run:e=>$(()=>Sl(e))},{id:`regenerateMilitary`,name:`${u(`Regenerate`)}: ${u(`Military`)}`,aliases:`generate armies regiments`,run:()=>$(bl)},{id:`regeneratePopulation`,name:`${u(`Regenerate`)}: ${u(`Population`)}`,aliases:`generate people`,run:()=>$(ul)},{id:`regenerateGoods`,name:`${u(`Regenerate`)}: ${u(`Goods`)}`,aliases:`generate resources`,run:()=>$(pl)},{id:`regenerateMarkets`,name:`${u(`Regenerate`)}: ${u(`Markets`)}`,aliases:`generate economy`,run:()=>$(ml)},{id:`regenerateProduction`,name:`${u(`Regenerate`)}: ${u(`Production`)}`,aliases:`generate trade economy`,run:()=>$(gl)},{id:`regenerateEconomy`,name:`${u(`Regenerate`)}: ${u(`Economy`)}`,aliases:`generate trade`,run:()=>$(hl)},{id:`regenerateIce`,name:`${u(`Regenerate`)}: ${u(`Ice`)}`,aliases:`generate glaciers icebergs`,run:()=>$(xl)},{id:`zoomReset`,name:u(`Reset Zoom`),aliases:`fit view whole map`,run:()=>kn(1e3)},{id:`zoomIn`,name:u(`Zoom In`),aliases:`view closer`,run:()=>En(1.2)},{id:`zoomOut`,name:u(`Zoom Out`),aliases:`view farther`,run:()=>En(.8)},{id:`toggleOptions`,name:u(`Toggle Menu`),aliases:`options panel show hide`,run:()=>Rc()},{id:`layersTab`,name:u(`Layers Tab`),link:!0,aliases:`menu panel`,run:()=>zc(`layersTab`)},{id:`styleTab`,name:u(`Style Tab`),link:!0,aliases:`menu panel editor`,run:()=>zc(`styleTab`)},{id:`optionsTab`,name:u(`Options Tab`),link:!0,aliases:`menu panel settings`,run:()=>zc(`optionsTab`)},{id:`toolsTab`,name:u(`Tools Tab`),link:!0,aliases:`menu panel`,run:()=>zc(`toolsTab`)},{id:`aboutTab`,name:u(`About Tab`),link:!0,aliases:`menu panel info credits`,run:()=>zc(`aboutTab`)},{id:`exportSvg`,name:u(`Export as SVG`),aliases:`download vector image`,run:()=>B.ExportMap.exportToSvg()},{id:`exportPng`,name:u(`Export as PNG`),aliases:`download image`,run:()=>B.ExportMap.exportToPng()},{id:`exportJpeg`,name:u(`Export as JPEG`),aliases:`download image`,run:()=>B.ExportMap.exportToJpeg()},{id:`exportTiles`,name:u(`Export as PNG Tiles`),aliases:`download zip`,run:()=>Sc()},{id:`exportJsonFull`,name:`${u(`Export to JSON`)}: ${u(`Full`)}`,aliases:`download data`,run:()=>B.ExportJson.exportToJson(`Full`)},{id:`exportJsonMinimal`,name:`${u(`Export to JSON`)}: ${u(`Minimal`)}`,aliases:`download data`,run:()=>B.ExportJson.exportToJson(`Minimal`)},{id:`exportJsonPackCells`,name:`${u(`Export to JSON`)}: ${u(`Pack cells`)}`,aliases:`download data`,run:()=>B.ExportJson.exportToJson(`PackCells`)},{id:`exportJsonGridCells`,name:`${u(`Export to JSON`)}: ${u(`Grid cells`)}`,aliases:`download data`,run:()=>B.ExportJson.exportToJson(`GridCells`)},{id:`exportGeoJsonCells`,name:`${u(`Export to GeoJSON`)}: ${u(`Cells`)}`,aliases:`download gis`,run:()=>B.ExportMap.saveGeoJsonCells()},{id:`exportGeoJsonRoutes`,name:`${u(`Export to GeoJSON`)}: ${u(`Routes`)}`,aliases:`download gis`,run:()=>B.ExportMap.saveGeoJsonRoutes()},{id:`exportGeoJsonRivers`,name:`${u(`Export to GeoJSON`)}: ${u(`Rivers`)}`,aliases:`download gis`,run:()=>B.ExportMap.saveGeoJsonRivers()},{id:`exportGeoJsonMarkers`,name:`${u(`Export to GeoJSON`)}: ${u(`Markers`)}`,aliases:`download gis`,run:()=>B.ExportMap.saveGeoJsonMarkers()},{id:`exportGeoJsonZones`,name:`${u(`Export to GeoJSON`)}: ${u(`Zones`)}`,aliases:`download gis`,run:()=>B.ExportMap.saveGeoJsonZones()},{id:`exportCsvBurgs`,name:`${u(`Export to CSV`)}: ${u(`Burgs`)}`,aliases:`download table settlements cities towns`,run:()=>L.BurgsOverview.exportCsv()},{id:`exportCsvBiomes`,name:`${u(`Export to CSV`)}: ${u(`Biomes`)}`,aliases:`download table environment terrain`,run:()=>L.BiomesEditor.exportCsv()},{id:`exportCsvRelations`,name:`${u(`Export to CSV`)}: ${u(`Relations`)}`,aliases:`download table diplomacy matrix`,run:()=>L.DiplomacyOverview.exportCsv()},{id:`exportCsvGoods`,name:`${u(`Export to CSV`)}: ${u(`Goods`)}`,aliases:`download table resources economy`,run:()=>L.GoodsEditor.exportCsv()},{id:`exportCsvMarkers`,name:`${u(`Export to CSV`)}: ${u(`Markers`)}`,aliases:`download table points of interest`,run:()=>L.MarkersOverview.exportCsv()},{id:`exportCsvMarkets`,name:`${u(`Export to CSV`)}: ${u(`Markets`)}`,aliases:`download table economy trade`,run:()=>L.MarketsOverview.exportCsv()},{id:`exportCsvMilitary`,name:`${u(`Export to CSV`)}: ${u(`Military`)}`,aliases:`download table armies forces`,run:()=>L.MilitaryOverview.exportCsv()},{id:`exportCsvRegiments`,name:`${u(`Export to CSV`)}: ${u(`Regiments`)}`,aliases:`download table military armies`,run:()=>L.RegimentsOverview.exportCsv()},{id:`exportCsvNotes`,name:`${u(`Export to CSV`)}: ${u(`Notes`)}`,aliases:`download table lore legends descriptions`,run:()=>L.NotesEditor.exportCsv()},{id:`exportCsvZones`,name:`${u(`Export to CSV`)}: ${u(`Zones`)}`,aliases:`download table areas regions`,run:()=>L.ZonesEditor.exportCsv()},{id:`showInfo`,name:u(`Show App Info`),link:!0,aliases:`about version help`,run:()=>lc()},{id:`getApp`,name:u(`Get Desktop App`),aliases:`install download electron`,run:()=>B.AppOffer.open()},{id:`toggleSaveReminder`,name:u(`Toggle Save Reminder`),aliases:`autosave notification`,run:()=>qi()},{id:`optionsReset`,name:u(`Reset Options`),aliases:`restore defaults clear cache reload`,run:()=>Sn()},{id:`savePresetButton`,name:u(`Save Layers Preset`),aliases:`displayed layers`,run:()=>Xc()},...Object.entries(Qn).map(([e,t])=>({id:`preset:${e}`,name:u(`Apply Layers Preset: {{- preset}}`,{preset:t}),aliases:`layers preset show`,run:()=>Yc(e)})),...[...Jn].map(([e,t])=>({id:`layer:${e}`,name:u(`Toggle {{- layer}}`,{layer:t.label}),aliases:`layer visibility show hide`,layer:e,run:()=>w.toggle(e)}))];function al(e){let t=e.trim();return t.includes(`?`)||/^(how|what|why|where|when|which|who|can|could|should|is|are|do|does|did|will|would)\s+\S/i.test(t)}function $(e){let t=()=>{e(),nl()};if(sessionStorage.getItem(`regenerateFeatureDontAsk`)){t();return}let n=()=>{M(`regenerateDontAsk`)?.checked&&sessionStorage.setItem(`regenerateFeatureDontAsk`,`true`)};F.confirm({title:u(`Regenerate element`),message:`${u(`Regeneration will remove all the custom changes for the element.`)}<br><br>${u(`Are you sure you want to proceed?`)}
      <div style="margin-top: 0.6em">
        <input id="regenerateDontAsk" class="checkbox" type="checkbox" />
        <label for="regenerateDontAsk" class="checkbox-label"><i>${u(`Do not ask again`)}</i></label>
      </div>`,confirm:u(`Proceed`),onConfirm:()=>{n(),t()},onCancel:n})}function ol(){for(let e of pack.states)e.i&&!e.removed&&e.label&&delete e.label;w.draw(`labels`)}function sl(){Te.generate(),w.draw(`relief`)}function cl(){_.regenerate(),w.draw(`routes`)}function ll(){we.regenerate(),_.sync(),w.draw(`rivers`)}function ul(){he.regenerate(),w.draw(`population`,`goods`)}function dl(){let{warning:e,error:t}=z.regenerate();if(t)return void I(t,!1,`error`);e&&I(e,!1,`warn`),dt(),w.draw(`states`,`borders`,`provinces`,`labels`,`burgIcons`,`military`,`goods`,`emblems`)}function fl(){ge.regenerate(),w.draw(`burgIcons`,`labels`,`routes`,`population`,`goods`,`emblems`)}function pl(){g.regenerate(),w.draw(`goods`)}function ml(){rn.regenerate(),w.draw(`markets`,`goods`,`trade`)}function hl(){an.regenerateEconomy(),w.draw(`markets`,`goods`,`trade`)}function gl(){an.regenerate(),w.draw(`goods`,`trade`)}function _l(){ie.regenerate(),w.draw(`emblems`)}function vl(){Ir.regenerate(),w.draw(`religions`,`goods`)}function yl(){de.regenerate(),w.draw(`cultures`,`goods`)}function bl(){ke.regenerate(),w.draw(`military`)}function xl(){Bn.regenerate(),w.draw(`ice`)}function Sl(e){function t(e){Er.regenerate(e),nl(),w.draw(`zones`,`goods`)}!e||!nt(e)?t(Mt(1,.5,.6,5,2)):F.prompt(u(`Please provide zones number multiplier`),{default:1,step:.01,min:0,max:100},e=>t(e))}var Cl=`
  <div class="separator">${u(`Edit`)}</div>
  <div class="grid">
    <button id="editBiomesButton" data-tip="${u(`Biomes Editor`)}" data-shortcut="Shift + B">
      ${u(`Biomes`)}
    </button>
    <button id="overviewBurgsButton" data-tip="${u(`Burgs Overview`)}" data-shortcut="Shift + T">
      ${u(`Burgs`)}
    </button>
    <button
      id="editCoastlineSettings"
      data-tip="${u(`Coastline Settings`)}"
    >
      ${u(`Coastlines`)}
    </button>
    <button id="editCulturesButton" data-tip="${u(`Cultures Editor`)}" data-shortcut="Shift + C">
      ${u(`Cultures`)}
    </button>
    <button
      id="editDiplomacyButton"
      data-tip="${u(`Diplomacy Overview`)}"
      data-shortcut="Shift + D"
    >
      ${u(`Diplomacy`)}
    </button>
    <button id="editEmblemButton" data-tip="${u(`Edit Emblem`)}" data-shortcut="Shift + Y">
      ${u(`Emblems`)}
    </button>
    <button id="overviewFeaturesButton" data-tip="${u(`Geographical Features Overview`)}" data-shortcut="Shift + F">
      ${u(`Features`)}
    </button>
    <button id="editGoods" data-tip="${u(`Goods Editor`)}" data-shortcut="Shift + G">${u(`Goods`)}</button>
    <button
      id="editHeightmapButton"
      data-tip="${u(`Click to open Heightmap customization menu`)}"
      data-shortcut="Shift + H"
    >
      ${u(`Heightmap`)}
    </button>
    <button id="overviewMarkersButton" data-tip="${u(`Markers Overview`)}" data-shortcut="Shift + K">
      ${u(`Markers`)}
    </button>
    <button id="overviewMarketsButton" data-tip="${u(`Markets Overview`)}">
      ${u(`Markets`)}
    </button>
    <button id="editMeasurersButton" data-tip="${u(`Measurers Editor`)}" data-shortcut="Shift + =">
      ${u(`Measurers`)}
    </button>
    <button id="overviewLabelsButton" data-tip="${u(`Labels Overview`)}" data-shortcut="Shift + L">
      ${u(`Labels`)}
    </button>
    <button
      id="overviewMilitaryButton"
      data-tip="${u(`Military Overview`)}"
      data-shortcut="Shift + M"
    >
      ${u(`Military`)}
    </button>
    <button id="editNamesBaseButton" data-tip="${u(`Namesbase Editor`)}" data-shortcut="Shift + N">
      ${u(`Namesbase`)}
    </button>
    <button id="editNotesButton" data-tip="${u(`Notes Editor`)}" data-shortcut="Shift + O">${u(`Notes`)}</button>
    <button id="editProvincesButton" data-tip="${u(`Provinces Editor`)}" data-shortcut="Shift + P">
      ${u(`Provinces`)}
    </button>
    <button id="editReligions" data-tip="${u(`Religions Editor`)}" data-shortcut="Shift + R">
      ${u(`Religions`)}
    </button>
    <button id="overviewRiversButton" data-tip="${u(`Rivers Overview`)}" data-shortcut="Shift + V">
      ${u(`Rivers`)}
    </button>
    <button id="overviewRoutesButton" data-tip="${u(`Routes Overview`)}" data-shortcut="Shift + U">
      ${u(`Routes`)}
    </button>
    <button id="overviewJourneysButton" data-tip="${u(`Journeys Overview`)}" data-shortcut="Shift + J">
      ${u(`Journeys`)}
    </button>
    <button id="editStatesButton" data-tip="${u(`States Editor`)}" data-shortcut="Shift + S">
      ${u(`States`)}
    </button>
    <button id="editTradeAnimationButton" data-tip="${u(`Trade Animation Editor`)}">
      ${u(`Trade`)}
    </button>
    <button id="editUnitsButton" data-tip="${u(`Units Editor`)}" data-shortcut="Shift + Q">${u(`Units`)}</button>
    <button id="editZonesButton" data-tip="${u(`Zones Editor`)}" data-shortcut="Shift + Z">${u(`Zones`)}</button>
  </div>
  <div class="separator">${u(`Regenerate`)}</div>
  <div id="regenerateFeature" class="grid">
    <button
      id="regenerateBurgs"
      data-tip="${m(u(`Click to regenerate all unlocked burgs and routes`),u(`States will remain as they are`),u(`Note: burgs are only generated in populated areas with culture assigned`))}"
    >
      ${u(`Burgs`)}
    </button>
    <button id="regenerateCultures" data-tip="${u(`Click to regenerate non-locked cultures`)}">${u(`Cultures`)}</button>
    <button
      id="regenerateEconomy"
      data-tip="${u(`Rebuild market territories, production, trade deals, and taxes from the current goods and markets`)}"
    >
      ${u(`Economy`)}
    </button>
    <button id="regenerateEmblems" data-tip="${u(`Click to regenerate all emblems`)}">${u(`Emblems`)}</button>
    <button id="regenerateGoods" data-tip="${u(`Regenerate bonus goods placement`)}">${u(`Goods`)}</button>
    <button id="regenerateIce" data-tip="${u(`Click to regenerate icebergs and glaciers`)}">${u(`Ice`)}</button>
    <button
      id="regenerateStateLabels"
      data-tip="${u(`Click to update state labels placement based on current borders`)}"
    >
      ${u(`State Labels`)}
    </button>
    <button id="regenerateMarkers" data-tip="${u(`Click to configure markers generation and regenerate unlocked markers`)}">
      ${u(`Markers`)}
    </button>
    <button id="regenerateMarkets" data-tip="${u(`Regenerate markets and their territories`)}">
      ${u(`Markets`)}
    </button>
    <button
      id="regenerateMilitary"
      data-tip="${u(`Recalculate military forces based on current options`)}"
    >
      ${u(`Military`)}
    </button>
    <button id="regeneratePopulation" data-tip="${u(`Click to recalculate rural and urban population`)}">
      ${u(`Population`)}
    </button>
    <button
      id="regenerateProduction"
      data-tip="${u(`Regenerate production and trade deals`)}"
    >
      ${u(`Production`)}
    </button>
    <button
      id="regenerateProvinces"
      data-tip="${m(u(`Click to select states and regenerate their non-locked provinces`),u(`States will remain as they are`))}"
    >
      ${u(`Provinces`)}
    </button>
    <button
      id="regenerateReliefIcons"
      data-tip="${u(`Click to regenerate all relief icons based on current cell biome and elevation`)}"
    >
      ${u(`Relief`)}
    </button>
    <button id="regenerateReligions" data-tip="${u(`Click to regenerate non-locked religions`)}">${u(`Religions`)}</button>
    <button id="regenerateRivers" data-tip="${u(`Click to regenerate all rivers (restore default state)`)}">
      ${u(`Rivers`)}
    </button>
    <button id="regenerateRoutes" data-tip="${u(`Click to regenerate all unlocked routes`)}">${u(`Routes`)}</button>
    <button
      id="regenerateStates"
      data-tip="${u(`Click to regenerate non-locked states. Emblems and military forces will be regenerated as well, burgs will remain as they are, but capitals will be different`)}"
    >
      ${u(`States`)}
    </button>
    <button
      id="regenerateZones"
      data-tip="${u(`Click to regenerate zones. Hold Ctrl and click to set zones number multiplier`)}"
    >
      ${u(`Zones`)}
    </button>
  </div>
  <div class="separator">${u(`Add`)}</div>
  <div id="addFeature" class="grid">
    <button
      id="addBurgTool"
      data-tip="${m(u(`Click on map to place a burg`),u(`Hold Shift to add multiple`))}"
      data-shortcut="Shift + 1"
    >
      ${u(`Burg`)}
    </button>
    <button
      id="addLabel"
      data-tip="${m(u(`Click on map to place label`),u(`Hold Shift to add multiple`))}"
      data-shortcut="Shift + 2"
    >
      ${u(`Label`)}
    </button>
    <button
      id="addMarker"
      data-tip="${m(u(`Click on map to place a marker`),u(`Hold Shift to add multiple`))}"
      data-shortcut="Shift + 3"
    >
      ${u(`Marker`)}
    </button>
    <input type="hidden" id="addedMarkerType" name="addedMarkerType" value="" />
    <button
      id="addRiver"
      data-tip="${m(u(`Click on map to place a river`),u(`Hold Shift to add multiple`))}"
      data-shortcut="Shift + 4"
    >
      ${u(`River`)}
    </button>
    <button id="addRoute" data-tip="${u(`Open route creation dialog`)}" data-shortcut="Shift + 5">${u(`Route`)}</button>
  </div>
  <div class="separator">${u(`Show`)}</div>
  <div class="grid">
    <button id="overviewCellsButton" data-tip="${u(`Cell Details`)}" data-shortcut="Shift + E">
      ${u(`Cells`)}
    </button>
    <button
      id="overviewChartsButton"
      data-tip="${u(`Data Charts`)}"
      data-shortcut="Shift + A"
    >
      ${u(`Charts`)}
    </button>
    <button id="openMinimapButton" data-tip="${u(`Click to open minimap overview. Click minimap to center view`)}">
      ${u(`Minimap`)}
    </button>
  </div>
  <div class="separator">${u(`Create`)}</div>
  <div class="grid">
    <button id="openSubmapTool" data-tip="${u(`Click to generate a submap from the current viewport`)}">${u(`Submap`)}</button>
    <button id="openTransformTool" data-tip="${u(`Click to transform the map`)}">${u(`Transform`)}</button>
    <button id="openWrapTool" data-tip="${u(`Adjust cell shapes with a brush`)}">${u(`Wrap`)}</button>
  </div>
`;N(`toolsContent`).innerHTML=Cl,N(`toolsContent`).addEventListener(`click`,e=>{if(options.app.mode)return I(u(`Exit customization mode first`),!1,`error`);if(!(e instanceof MouseEvent)||!(e.target instanceof HTMLElement)||e.target.tagName!==`BUTTON`)return;let t=il.find(t=>t.id===e.target.id);t&&t.run(e)});var wl=`ken burgan
Sera's Nafitlaan
Richard Rogers
Hylobate
Colin deSousa
Aurelia De La Silla
Maciej Kontny
Ricky L Cain
Iggyflare
Garrett Renner
Michael Harris
Joshua Maly
Nigel Guest
Theo Hodges
BERTHEAS Frédéric
lilMoni
Δημήτρης Μάρκογιαννακης
Lee S.
Chris Dibbs
jarrad tait
Jacen Solo
Hannes Rotestam
Preston Hicks
Лонгин
Will Fink
ControlFreq
IllAngel
John Giardina
Thiago Prado
Zhang Dijon
NoBurny
thibault tersinet
scarletsky 
Nich Smith
Omegus
Karl Abrahamsson
Sara Fernandes
peetey897
Cooper Janse
G F
Glen Aultman-Bettridge
Nathan Rogers
Benjamin Mock
CadmiumMan 
Kirk Edwards
Leigh G
Thom Colyer
Frederik
C pstj
Zachary Pecora
Trevor D'Arcey
Ryan Gauvin
Shawn Moore
Jim Channon
Kyarou
Actual_Dio
Jim B Johnson
Robert Rinne
Zion 
Kenji Yamada
DerWolf 
RLKZ1022
Neyimadd
Aaron Blair
Mira Cyr
Bird Law Expert
S A Rudy
Sam Spoerle
angel carrillo
Alden Z
Holly Loveless
Sea Wolf
Atenfox 
Cyberate
E. Jason Davis
Caro Lyns
David Kaul
Charlotte Wiland
Kyle Barrett
Ian Grau-Fay
cameron cannon
RedSpaz
John Wick
Randy Ross
Rita
Ele
Johnathan Xavier Hutchinson
Andrew Stein
Ghettov Milan
Malke
TameMoon
Daniel Cooper
Markus Peham
The Next Level
Alexander Whittaker
Sidr Dim
William Markus
Jordan
Pleaseworkforonce 
Damon Gallaty
Trentin Bergeron
Emarandzeb
Laulajatar
Dale McBane
Chris Kohut
Preston Mitchell
Andrew Kircher
Frank Fewkes
Moist mongol
Joshua Xiong
Jan Bundesmann
www15o
Game Master Pro
jason baldrick
Exp1nt
w 
Shubham Jakhotiya
Braxton Istace
LesterThePossum
Rurikid
ojacid .
james 
A Patreon of the Ahts
BigE0021
Angelique Badger
Jonathan Williams
AntiBlock 
Redsauz
Florian Kelber
John Patrick Callahan Jr
Alexandra Vesey
Bas Kroot
Dzmitry Malyshau
PedanticSteve
Josh Wren
BLRageQuit
Dario Spadavecchia
Neutrix 
Markell
Rocky
Robert Landry
Skylar Mangum-Turner
Nick Mowry
Anjen Pai
Hope You're Well
Alexandre Boivin
Racussa
Mike Conley
Karen Blythe
Mark Sprietsma
Xavier privé
Tommy Mayfield
Václav Švec
Binks
Mackenzie 
Linn Browning
Writer's Consultant Page by George J.Lekkas
Andrew Hines
Wexxler 
Jason Matthew Wuerfel
Milo Cohen
Alan Buehne
Dominick Ormsby
Espen Sæverud
Rasmus Legêne
rbbalderama
Nobody679
Prince of Morgoth
Jaryd Armstrong
Gary Smith
ThyHolyDevil
良义 金
Andrew Pirkola
Dig
Chris Gray
Tyshaun Wise
Phoenix
Ethan Cook
Jordan Bellah
Petro Lombaard
Kass Frisson
Lazer Elf
Gavin Madrigal
Rox
PinkEvil
Martin Lorber
Emanuel Pietri
Alex Beard
Jeffrey Henning
Eric Alexander Cartaya
Dust Bunny
GameNight 
Beingus
Crys Cain
Lon Varnadore
Thomas Mortensen Hansen
Drinarius
Ed Wright
Adrian Wright
Zklaus 
Chris Bloom
PlayByMail.Net
Maxim Lowe
Aquelion
Tiber
Daydream1013
Page One Project
Clonetone
Egoensis 
Brad Wardell
Heaven N Lee
BarnabyJones
Paul Ingram
Lance Saba
Chad Riley
Austin
Rowland Kingman
Decimus Vitalis
Grayson McClead
Battleturtle1
Kristin Chernoff
Justin Mcclain
Patrick Jones
Esther Busch
Chance Mena
JimmyTheBob
Antiroo 
Dalton Clark
Guilherme Aguiar
Simon Drapeau
Akirsop
Radovan Zapletal
Vanessa Anjos
Rikard Wolff
Justa Badge
teco 47
Jake
Miguel Alejandro
Blargh Blarghmoomoo
Jakob Siegel
Grant A. Murray
Jarno Hallikainen
Jan Ka
Joshua Vaught
MaxOliver 
WarWizardGames
Evan-DiLeo 
Eric Moore
Kyle S
Alex Debus
Uniquenameosaurus 
Dean Dunakin
Jack 
Bryan Brake
McNeil Atticus Inksmudge
Char 
Tom Van Orden jr
Kendall Patterson
Akylos 
Barna Csíkos
Nicholas Grabstas
OldFarkas
Riley Seaman
Daniel Gill
Kyle Robertson
Natasha Taylor
Pierrick Bertrand
Jared.K
Dylan Devenny
logic_error
SashaTK
Steve Johnson
MontyBoosh 
Achillain 
Jaden 
Vito Martono
Thirty-OneR 
Eric Foley
ThatGuyGW 
Dee Chiu
James H. Anthony
Kevin Cossutta
MadNomadMedia
Darinius Dragonclaw Studios
Tsahyla (Triston Lightyear)
Christopher Whitney
María Martín López
Annie Rishor
Aram Sabatés
Jeppe Skov Jensen
Martin Seeger
Oneiris (Oni)
EternalDeiwos
Richard Keating
StroboWolf 
Rick Falkvinge
Zewen Senpai
Adam Butler
Kassidy 
Sadie Blackthorne
ErrorForever 
Seth Fusion
Gus 
Paul 
Lucid 
Allen Varney
Hannah May
Sankroh
Eliot Miller
Detocroix 
Meg Ziegler
rob bee
Anoplexian 
Marten F
Erin D. Smale
Johnpaul Morrow
Roekai 
Drunken_Legends 
Jesse Holmes
Maxwell Hill
Jan Dvořák
SirTobit 
G0atfather
Allen S. Rout
Pippa Mitchell
Austin Miller
Caner Oleas Pekgönenç
Alison Bull Bear
Bradley Edwards
Tertiary 
Daniel
Joshua E Goodwin
Shaun Alexander
Ryan Lege
Myrrhlin
Jesper Cockx
Noirbard 
Dice
Brian Drennen
Giant Monster Games
Reya C.
Krk
Endwords 
Jacob Harrington
RK
Michael Greiner
Steven Bennett
Brice Moss
Whakomatic x
Stephen Herron
kosmobius
ZizRenanim
Barished 
Maur Razimtheth
Aaron bateson
Diklyquill
Shawn Taylor
Brady R Rathbun
FlippantFeline 
Shadow
J 
Tamashi Toh
Huw Williams
Graves
ShadeByTheSea
The Dungeon Masters
Valerie Elise
Empi3
William Pucs
Michael Carmody
Marco Veldman
naikibens220
Jordon Phillips
_gfx_ 
F. Casanova
Jared McDaris
BlastWind 
Taldonix
Connor McMartin
Nexoness 
Guy 
Maggie 
AdvancedAzrielAngel
Alfred García
Norbert Žigmund
Jennifer
Titanium Tomes
John Ackley
Invad3r233
Jonathan Killstring
Jessica Thomas
Nikita Kondratjuks
Steve Hyatt
PoliticsBuff 
Ian arless
Karnat 
Hilton Williams
Kevin 
Katharina Haase
Hisham Bedri
Bird
JOSHUA QUALTIERI
Preston Brooks
Troy Schuler
DerGeisterbär 
L. V. Werneck
Marcus Hellyrr
yami
Daniel Eric Crosby
Augusto Chiarle
Doug Churchman
David Roza
Alexander Thomas
Ashley Wilson-Savoury
Nathan L Myers
Theresa Walsh
JP Roberts III
William Henry
OldbeanOldboy
Javasharp
Diagonath 
Gun Metal Games
Scott Marner
Alloyed Clavicle
Valerii Matskevych
Spencer Sherman
Nolan Moore
James Schellenger
Pat 
Dino Princip
Shawn Spencer
Timothée CALLET
KC138
Nylian 
Kate 
Markus Finster
CanadianGold 
AstralJacks 
Keith Marshall
Scott Davis
Joseph Miranda
Shaptarshi Joarder
Branndon
EP
Johan Fröberg
Sasquatch 
Chase Mayers
Sizz_TV 
Ryan Westcott
Nathan Mitchell
Curt Flood
Mikey 
E.M. White
Billy 
Vlad Tomash
Xariun
Luke Nelson
W Maxwell Cassity-Guilliom
Marty H
Aaron Meyer
Max Amillios
chris 
cyninge 
Omegavoid 
Fritjof Olsson
Crazypedia 
Duncan Thomson
William Merriott
Gold Tamarin
Lhoris 
Jonathan
Jon
Massimo Vella
Feuver 
aymeric 
Eric Schumann
Rei 
Fondue 
Paavi1
Wil Sisney
David Patterson
L
Justin Scheffers
Commieboo
Garrison Wood
Emsiron
Frosty
John Joseph Adams
The_Lone_Wanderer
Andrew Stein
Groonfish
soup
Bruno Haack Vilar
Ian Burke
Tentacle Shogun
Andrew Chandler
Fritz Wulfram
Doom Chupacabra
Zakharov
Dylan Fox
Alfred Piccioni
Avery Vreeland
Kennedy
Zack Wolf
Matjam
Jeff Johnston
Hunter Hawthorne
Sunsette 
Travis Love
Dakian Delomast
Kyle
Davis Walker
Naomi
Clément D
Jake Herr
ReV0LT
Jack Dawson
Queso y Libertad
RadioJay21H
NEO
Crecs
A AASD
Mikhail Ushakov
NoFun
AmbiguousCake
Madeline Naiman
2FingerzDown
Josiah Lulf
Vector Tragedy
yann
Blarghle Hargle
Jelke Boonstra
afistupmabum
Rob Frantz
Driver
Tr4v3l3r
Cooper Cantrell
Maximilien Bouillot
J.E. Ellis
Igor
John Todd
burning.rosary
Shane Roppel
Hank Agrippa
Noah Morris
Phil Karecki
Matthew Jarocki
Lucius Licinius Lucullus
Andrew Haney
Noah Morris
Phil Karecki
Matthew Jarocki
Lucius Licinius Lucullus
Andrew Haney
Jesse Luke
Lord_Luce
Neko no Maigo
Hossyboy 
Yasui Masatake
Jesse Roy
Remain
Douglas Rector
J Clark
Raine Logan
Matty Ice
DieMuetze
Dan Popoli
Marwyn
Kederalia
Whyse Wytch
Elliyevee
James Miller
Pirate Fish
David Leitner
Vyritecht
emre
Don't mail me
Isaac Wooten
MisterPete
Johanna Martin
Marmalade_MacGuffin
James Benware
FortunesFaded
breadsticks
Murderbits
Ben Jones
Marco Faltracco
L
silentArtifact
Keith Potter
Morgan Gilbert
Alengork Gamer
Don Johnson
Mish
effervescent
Trevor Sansom
Eric Christian Berg
Jamin
Aurelia De La Sella
morgan
Barry Gill
Wolf
Titan_650
Sebastian Tampu
dr_not_sam
Mie96
Riley
Amber Davis
tomtom1969vlbg
Eric Knight
Adeline Lefizelier
Jerry Palmer
Colin Lewis
ｌうｃｙ
Peyton
Silvershade
jim8333
Kevin
Jeffrey Brown
Tyler Riggs
Justin Warrington
Sovrynth Systems
Coffee
Justin
Paul Facknitz
William Fichou
Morphine
ussis6nad
Ælyndor
Patrick McEntee
y John
Sean O'Daniels
ShadowMole
FlightlessDutchman
Gawain Yeo
Tom Hollingworth
Scott Gunn
Gabe Hurd
Benjamin Sardinsky
Task_Failer
Gawain Yeo
Tom Hollingworth
Scott Gunn
Gabe Hurd
Benjamin Sardinsky
Task_Failer
Sable Crow
HaginZuria
Conor Pewterbaugh
Warren
f
YeOldeRaven`,Tl=`https://github.com/Azgaar/Fantasy-Map-Generator`,El=`${Tl}/wiki`,Dl=`
  <div class="aboutActions">
    <button
      id="startTourButton"
      data-tip="${u(`Take an interactive tour of the map generator`)}"
      style="flex: 1; border: 1px solid var(--header);"
    >
      ${u(`Interactive Tour`)}
    </button>
    <button
      id="getAppButton"
      data-tip="${u(`Install the Generator on your computer`)}"
      style="flex: 1; border: 1px solid var(--header);"
    >
      ${u(`Desktop App`)}
    </button>
  </div>
  <p>
    ${m(u(`{{- generator}} is an {{- openSource}} tool by Azgaar and Team.`,{generator:C(Tl,u(`Fantasy Map Generator`)),openSource:C(`${Tl}/blob/master/LICENSE`,u(`open source`))}),u(`You may use maps as they are, edit them or even create a new map from scratch.`),u(`Check out the {{- quickStart}}, {{- qaa}}, {{- video}} and {{- hotkeys}} for guidance.`,{quickStart:C(`${El}/Quick-Start-Tutorial`,u(`Quick start tutorial`)),qaa:C(`${El}/Q&A`,u(`Q&A page`)),video:C(`https://youtube.com/playlist?list=PLtgiuDC8iVR2gIG8zMTRn7T_L0arl9h1C`,u(`Video tutorial`)),hotkeys:C(`${El}/Hotkeys`,u(`hotkeys`))}))}
  </p>
  <p>
    ${m(u(`Join our {{- discord}} and {{- reddit}} to ask questions, get help and share maps.`,{discord:C(`https://discordapp.com/invite/X7E84HU`,u(`Discord server`)),reddit:C(`https://www.reddit.com/r/FantasyMapGenerator/`,u(`Reddit community`))}),u(`The created maps can be used for free, even for commercial purposes.`))}
  </p>
  <p>
    ${m(u(`The project is under active development.`),u(`Creator and main maintainer: Azgaar.`),u(`To track the development progress see the {{- devboard}}.`,{devboard:C(`https://trello.com/b/7x832DG4/fantasy-map-generator`,u(`devboard`))}),u(`For older versions see the {{- changelog}}.`,{changelog:C(`${El}/Changelog`,u(`changelog`))}),u(`Please report bugs {{- here}}.`,{here:C(`${Tl}/issues`,u(`here`))}),u(`You can also contact me directly via {{- email}}.`,{email:`<a href="mailto:azgaar.fmg@yandex.by" target="_blank">${u(`email`)}</a>`}))}
  </p>
  <div
    style="
      background-color: #e85b46;
      padding: 0.4em;
      width: max-content;
      margin: 0.6em auto 0 auto;
      border: 1px solid #943838;
    "
  >
    <a
      href="https://www.patreon.com/azgaar"
      target="_blank"
      style="color: white; text-decoration: none; font-family: sans-serif"
    >
      <div>
        <div style="width: 0.8em; display: inline-block; padding: 0 0.2em; fill: white">
          <svg viewBox="0 0 569 546">
            <circle cx="362.589996" cy="204.589996" data-fill="1" id="Oval" r="204.589996" />
            <rect data-fill="2" height="545.799988" id="Rectangle" width="100" x="0" y="0" />
          </svg>
        </div>
        ${u(`SUPPORT ON PATREON`)}
      </div>
    </a>
  </div>
  <p>
    ${u(`Thanks for all supporters on {{- patreon}}!`,{patreon:`<a id="supportersLink" data-tip="${u(`Click to see list of supporters`)}">Patreon</a>`})}
  </p>
  <div style="display: flex; justify-content: center; padding: 0.4em; font-family: cursive">
    <a href="https://u24.gov.ua/" style="width: 80%" data-tip="${u(`Support Ukraine`)}" target="_blank">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 200">
        <rect width="100%" height="100%" fill="#005bbb"></rect>
        <rect y="50%" width="100%" height="50%" fill="#ffd500"></rect>
        <text x="50%" text-anchor="middle" font-size="5em" y="32%" fill="#f5f5f5">${u(`Support Ukraine`)}</text>
        <text x="50%" text-anchor="middle" font-size="4em" y="78%" fill="#005bdd">u24.gov.ua</text>
      </svg>
    </a>
  </div>
  <div style="text-align: left">
    <p>${u(`Check out our other projects`)}:</p>
    <div>• <a href="https://azgaar.github.io/Armoria" target="_blank">Armoria</a>: ${u(`a tool for creating coats of arms`)}</div>
    <div>• <a href="https://deorum.vercel.app" target="_blank">Deorum</a>: ${u(`gallery of fantasy characters`)}</div>
  </div>
  <ul class="share-buttons">
    <li>
      <a
        href="https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fazgaar.github.io%2FFantasy-Map-Generator%2F&quote="
        data-tip="${u(`Share on Facebook`)}"
        target="_blank"
        ><img alt="${u(`Share on Facebook`)}" src="images/Facebook.png" loading="lazy"
      /></a>
    </li>
    <li>
      <a
        href="https://twitter.com/intent/tweet?source=https%3A%2F%2Fazgaar.github.io%2FFantasy-Map-Generator&text=%23FantasyMapGenerator%0A%0Ahttps%3A//azgaar.github.io/Fantasy-Map-Generator"
        target="_blank"
        data-tip="${u(`Tweet`)}"
        ><img alt="${u(`Tweet`)}" src="images/Twitter.png" loading="lazy"
      /></a>
    </li>
    <li>
      <a
        href="http://pinterest.com/pin/create/button/?url=https%3A%2F%2Fazgaar.github.io%2FFantasy-Map-Generator"
        target="_blank"
        data-tip="${u(`Pin it`)}"
        ><img alt="${u(`Pin it`)}" src="images/Pinterest.png" loading="lazy"
      /></a>
    </li>
    <li>
      <a
        href="http://www.reddit.com/submit?url=https%3A%2F%2Fazgaar.github.io%2FFantasy-Map-Generator"
        target="_blank"
        data-tip="${u(`Submit to Reddit`)}"
        ><img alt="${u(`Submit to Reddit`)}" src="images/Reddit.png" loading="lazy"
      /></a>
    </li>
    <li>
      <a href="https://discord.gg/X7E84HU" target="_blank" data-tip="${u(`Join Discord server`)}"
        ><img alt="${u(`Join Discord server`)}" src="images/Discord.png" loading="lazy"
      /></a>
    </li>
  </ul>
`;N(`aboutContent`).innerHTML=Dl;function Ol(){let e=window.innerWidth<800?2:5,t=wl.split(`
`).sort();F.message({title:u(`Patreon supporters`),width:`min-width`,message:`<ul style="column-count: ${e}; column-gap: 2em">${t.map(e=>`<li>${e}</li>`).join(``)}</ul>`})}N(`startTourButton`).addEventListener(`click`,()=>B.UiTour.start()),N(`getAppButton`).addEventListener(`click`,()=>B.AppOffer.open()),N(`supportersLink`).addEventListener(`click`,Ol),document.addEventListener(`keydown`,kl),document.addEventListener(`keyup`,Al);function kl(e){if(!Pl())return;let{code:t,ctrlKey:n,metaKey:r,altKey:i,shiftKey:a}=e;(n||r)&&t===`KeyS`?(e.preventDefault(),e.repeat||B.Save.toMachine(a)):(i&&!n&&!a&&e.preventDefault(),n&&[`KeyS`,`KeyC`].includes(t)&&e.preventDefault(),[`F1`,`F2`,`F6`,`F9`,`Tab`].includes(t)&&e.preventDefault())}function Al(e){if(!Pl()||(e.stopPropagation(),options.map.viewOnly&&!Ml(e)))return;let{code:t,key:n,ctrlKey:r,metaKey:i,shiftKey:a,altKey:o}=e,s=r||i||n===`Control`;if(s&&t===`KeyS`)return;let c=(a||n===`Shift`)&&!o,l=o&&(a||n===`Shift`)&&!s,u=$n(t),d=Fl();if(t===`Space`)Nl(e);else if(t===`F1`)lc();else if(t===`F2`)Mo();else if(t===`F6`)B.Save.toStorage();else if(t===`F9`)B.Load.quickLoad();else if(t===`Tab`)Rc(e);else if(t===`Escape`)F.closeAll(),Lc();else if(t===`Delete`)Rl();else if(t===`KeyO`&&M(`canvas3d`))L.View3d.toggleOptions();else if(s&&t===`KeyQ`)qi();else if(s&&t===`KeyC`)B.Save.toDropbox();else if(s&&t===`KeyZ`)M(`undo`)?.click();else if(s&&t===`KeyY`)M(`redo`)?.click();else if((c||l)&&t===`KeyH`)L.HeightmapEditor.open();else if((c||l)&&t===`KeyB`)L.BiomesEditor.open();else if((c||l)&&t===`KeyS`)L.StatesEditor.open();else if((c||l)&&t===`KeyP`)L.ProvincesEditor.open();else if((c||l)&&t===`KeyD`)L.DiplomacyOverview.open();else if((c||l)&&t===`KeyL`)L.LabelsOverview.open();else if((c||l)&&t===`KeyC`)L.CulturesEditor.open();else if((c||l)&&t===`KeyN`)L.NamesbaseEditor.open();else if((c||l)&&t===`KeyZ`)L.ZonesEditor.open();else if((c||l)&&t===`KeyR`)L.ReligionsEditor.open();else if((c||l)&&t===`KeyY`)L.EmblemsEditor.openDefault();else if((c||l)&&t===`KeyQ`)L.UnitsEditor.open();else if((c||l)&&t===`KeyO`)L.NotesEditor.open();else if((c||l)&&t===`KeyA`)L.ChartsOverview.open();else if((c||l)&&t===`KeyT`)L.BurgsOverview.open();else if((c||l)&&t===`KeyU`)L.RoutesOverview.open();else if((c||l)&&t===`KeyF`)L.FeaturesOverview.open();else if((c||l)&&t===`KeyV`)L.RiversOverview.open();else if((c||l)&&t===`KeyM`)L.MilitaryOverview.open();else if((c||l)&&t===`KeyK`)L.MarkersOverview.open();else if((c||l)&&t===`KeyE`)L.CellInfo.open();else if((c||l)&&t===`KeyG`)L.GoodsEditor.open();else if((c||l)&&t===`KeyJ`)L.JourneysOverview.open();else if((c||l)&&t===`KeyW`)L.WrapTool.open();else if((c||l)&&t===`Equal`&&!d)L.MeasurersEditor.open();else if(n===`!`)L.BurgCreator.toggle();else if(n===`@`)L.LabelCreator.toggle();else if(n===`#`)L.MarkerCreator.toggle();else if(n===`$`)L.RiverAutoCreator.toggle();else if(n===`%`)L.RouteCreator.open();else if(t===`BracketRight`)Ll(t);else if(t===`BracketLeft`&&Ll(t))return;else u&&(t!==`Equal`||!options.app.mode&&!d)?w.toggle(u):t===`ArrowLeft`?Dn(10,0):t===`ArrowRight`?Dn(-10,0):t===`ArrowUp`?Dn(0,10):t===`ArrowDown`?Dn(0,-10):n===`+`||n===`-`||n===`=`?Il(n,d):n===`0`?kn(1e3):n===`1`?V(1):n===`2`?V(2):n===`3`?V(3):n===`4`?V(4):n===`5`?V(5):n===`6`?V(6):n===`7`?V(7):n===`8`?V(8):n===`9`&&V(9)}var jl=[`Space`,`F1`,`F2`,`F9`,`Tab`,`Escape`,`KeyO`,`ArrowLeft`,`ArrowRight`,`ArrowUp`,`ArrowDown`];function Ml({code:e,key:t,ctrlKey:n,metaKey:r,altKey:i,shiftKey:a}){return n||r||i?!1:jl.includes(e)?!0:/^[\d=+-]$/.test(t)?!(a&&e===`Equal`):!a&&!!$n(e)}function Nl(e){if(e.ctrlKey||e.metaKey||e.altKey||e.shiftKey||Fl())return;let t=document.activeElement;t&&t!==document.body||L.Omnibar.open()}function Pl(){let e=document.activeElement,t=e?.tagName,n=e?.contentEditable;return!([`INPUT`,`SELECT`,`TEXTAREA`].includes(t??``)||t===`DIV`&&n===`true`||document.getSelection()?.toString())}function Fl(){return[...document.querySelectorAll(`[data-brush-size]`)].find(e=>e.offsetParent)??null}function Il(e,n=Fl()){if(n){let r=Number(n.dataset.keyStep)||5,i=e===`-`?-r:r,a=Number(n.getAttribute(`min`))||5,o=Number(n.getAttribute(`max`))||100;n.value=String(t(+n.value+i,a,o)),n.dispatchEvent(new Event(`input`,{bubbles:!0}))}else En(e===`+`?1.2:.8)}function Ll(e){return!M(`brushesButtons`)?.querySelector(`button.pressed`)&&!Fl()?!1:(Il(e===`BracketLeft`?`-`:`+`),!0)}function Rl(){let e=Array.from(document.querySelectorAll(`[role='dialog'] .fastDelete`)).find(e=>e.style.display!==`none`);e&&e.click();let t=Array.from(document.querySelectorAll(`[role='dialog']`)).filter(e=>e.style.display!==`none`);t.length&&t.forEach(e=>{e.querySelectorAll(`button`).forEach(e=>{e.textContent===u(`Remove`)&&e.click()})})}var zl=new WeakMap;function Bl(e,t=`${e}Header`){let n=M(t);if(!n)return;let r=Wl(n);Kl(e,n),Ul(n);for(let t of Array.from(n.querySelectorAll(`.sortable`)))t.addEventListener(`click`,()=>Hl(e,t));qt.onReset(e,`sorting`,()=>{ql(n,r),Ul(n)})}function Vl(e,t){let n=t.classList.contains(`alphabetically`)?`name`:`number`,r=t.className.includes(`icon-sort`),i=t.className.includes(`-down`)?`-up`:`-down`;!r&&n===`name`&&(i=`-up`);let a=t.parentNode;for(let e of Array.from(a.querySelectorAll(`div.sortable`)))for(let t of Array.from(e.classList))t.includes(`icon-sort`)&&e.classList.remove(t);t.classList.add(`icon-sort-${n}${i}`),Gl(e,a)}function Hl(e,t){Vl(e,t),Ul(t.parentNode)}function Ul(e){let t=e.querySelector(`div[class*='icon-sort']`);if(!t)return;let n=t.dataset.sortby,r=t.classList.contains(`alphabetically`),i=t.className.includes(`-down`)?-1:1,a=e.nextElementSibling;Array.from(a.children).sort((e,t)=>{let a=r?e.dataset[n]:Number(e.dataset[n]),o=r?t.dataset[n]:Number(t.dataset[n]);return a===void 0||o===void 0?0:(a>o?1:a<o?-1:0)*i}).forEach(e=>{a.appendChild(e)})}function Wl(e){let t=e.querySelector(`div[class*='icon-sort']`);return t?{sortBy:t.dataset.sortby,alphabetically:t.classList.contains(`alphabetically`),direction:t.className.includes(`-down`)?-1:1}:null}function Gl(e,t){let n=Wl(t);n&&qt.set(e,`sorting`,n)}function Kl(e,t){let n=qt.get(e,`sorting`,()=>Wl(t));n&&(Array.from(t.querySelectorAll(`.sortable`)).find(e=>e.dataset.sortby===n.sortBy)?ql(t,n):qt.remove(e,`sorting`))}function ql(e,t){for(let t of Array.from(e.querySelectorAll(`.sortable`)))for(let e of Array.from(t.classList))e.includes(`icon-sort`)&&t.classList.remove(e);if(!t)return;let n=Array.from(e.querySelectorAll(`.sortable`)).find(e=>e.dataset.sortby===t.sortBy);if(!n)return;let r=n.classList.contains(`alphabetically`)?`name`:`number`,i=t.direction===-1?`down`:`up`;n.classList.add(`icon-sort-${r}-${i}`)}function Jl(e,t,n){let r=n[t.sortBy];if(!r)return e;let i=e.map(e=>({item:e,key:r(e)}));i.sort((e,n)=>{if(t.alphabetically){let r=String(e.key),i=String(n.key);return(r>i?1:r<i?-1:0)*t.direction}return(Number(e.key)-Number(n.key))*t.direction});for(let t=0;t<i.length;t++)e[t]=i[t].item;return e}function Yl(e,t){let n=N(`${e}Header`),r=Wl(n);Kl(e,n);for(let r of Array.from(n.querySelectorAll(`.sortable`)))r.addEventListener(`click`,()=>{Vl(e,r),t()});qt.onReset(e,`sorting`,()=>{zl.delete(n),ql(n,r),t()})}function Xl(e,t,n){let r=N(`${e}Header`),i=Wl(r);if(!i)return t;let a={};for(let e of n)e.sortBy&&(a[e.key]=e.sortBy);let o=[i,...(zl.get(r)||[]).filter(e=>e.sortBy!==i.sortBy)];zl.set(r,o);for(let e of o.toReversed())Jl(t,e,a);return t}var Zl=`
  fill-box:not([disabled]) {
    cursor: pointer;
  }

  fill-box > svg {
    vertical-align: middle;
    pointer-events: none;
  }

  fill-box > svg > rect {
    stroke: #666666;
    stroke-width: 2;
  }
`,Ql=document.createElement(`style`);Ql.setAttribute(`type`,`text/css`),Ql.innerHTML=Zl,document.head.appendChild(Ql);var $l=document.createElement(`template`);$l.innerHTML=`
  <svg>
    <rect x="0" y="0" width="100%" height="100%">
  </svg>
`;function eu(){I(this.tip)}var tu=class extends HTMLElement{constructor(){super(),this.appendChild($l.content.cloneNode(!0)),this.querySelector(`rect`)?.setAttribute(`fill`,this.fill),this.querySelector(`svg`)?.setAttribute(`width`,this.size),this.querySelector(`svg`)?.setAttribute(`height`,this.size)}connectedCallback(){this.addEventListener(`mousemove`,eu)}disconnectedCallback(){this.removeEventListener(`mousemove`,eu)}get fill(){return this.getAttribute(`fill`)||`#333`}set fill(e){this.setAttribute(`fill`,e),this.querySelector(`rect`)?.setAttribute(`fill`,e)}get size(){return this.getAttribute(`size`)||`1em`}get tip(){return this.dataset.tip||m(u(`Fill style`),u(`Click to change`))}};customElements.define(`fill-box`,tu);var nu=`
  slider-input {
    display: flex;
    align-items: center;
    gap: .4em;
  }
`,ru=document.createElement(`style`);ru.setAttribute(`type`,`text/css`),ru.innerHTML=nu,document.head.appendChild(ru);var iu=document.createElement(`template`);iu.innerHTML=`
  <input type="range" />
  <input type="number" />
`;var au=class extends HTMLElement{static observedAttributes=[`min`,`max`,`step`];constructor(){super(),this.appendChild(iu.content.cloneNode(!0));let e=this.querySelector(`input[type=range]`),t=this.querySelector(`input[type=number]`);e.min=t.min=this.getAttribute(`min`)||`0`,e.max=t.max=this.getAttribute(`max`)||`100`,e.step=t.step=this.getAttribute(`step`)||`1`,e.value=t.value=this.value||this.getAttribute(`value`)||`50`,e.addEventListener(`input`,this.handleEvent.bind(this)),t.addEventListener(`input`,this.handleEvent.bind(this)),e.addEventListener(`change`,this.handleEvent.bind(this)),t.addEventListener(`change`,this.handleEvent.bind(this))}attributeChangedCallback(e,t,n){if(n!==null)for(let t of this.querySelectorAll(`input`))t.setAttribute(e,n)}handleEvent(e){let t=e.target.value;if(Number.isNaN(Number(t))||t===``)return e.stopPropagation();let n=this.querySelector(`input[type=range]`),r=this.querySelector(`input[type=number]`);this.value=n.value=r.value=t,this.dispatchEvent(new CustomEvent(e.type,{detail:{value:t},bubbles:!0,composed:!0}))}set value(e){let t=this.querySelector(`input[type=range]`),n=this.querySelector(`input[type=number]`);t.value=n.value=e}get value(){return this.querySelector(`input[type=number]`).value}get valueAsNumber(){return this.querySelector(`input[type=number]`).valueAsNumber}};customElements.define(`slider-input`,au);var ou=(e,t)=>{P(`#debug`).selectAll(`text`).remove(),P(`#debug`).selectAll(`text`).data(e).enter().append(`text`).attr(`x`,(e,n)=>t[n][0]).attr(`y`,(e,n)=>t[n][1]).text(e=>e)},su=(e,t)=>{let n=bt(e),r=Nt(e),i=Pt.get(styles.heightmap.groups.landHeights.options.scheme);e=e.map(e=>1-ee(e,r,n)),P(`#debug`).selectAll(`polygon`).remove(),P(`#debug`).selectAll(`polygon`).data(e).enter().append(`polygon`).attr(`points`,(e,n)=>String(R.getPolygon(n,t))).attr(`fill`,e=>i(e)).attr(`stroke`,e=>i(e))},cu=e=>{P(`#debug`).select(`#connections`).remove();let t=P(`#debug`).append(`g`).attr(`id`,`connections`).attr(`stroke-width`,.8),n=e.cells.p,r=e.cells.routes;for(let e in r)for(let i in r[e]){let[a,o]=n[e],[s,c]=n[i],[l,u]=[(a+s)/2,(o+c)/2],d=r[e][i];t.append(`line`).attr(`x1`,a).attr(`y1`,o).attr(`x2`,l).attr(`y2`,u).attr(`data-id`,d).attr(`stroke`,Vt[d%12])}},lu=([e,t],{color:n=`red`,radius:r=.5})=>{P(`#debug`).append(`circle`).attr(`cx`,e).attr(`cy`,t).attr(`r`,r).attr(`fill`,n)},uu=(e,{color:t=`red`,width:n=.5})=>{let r=Ye().curve(qn);P(`#debug`).append(`path`).attr(`d`,l(r(e))).attr(`stroke`,t).attr(`stroke-width`,n).attr(`fill`,`none`)},du=`river-cells.river-points.river-ownership.river-ends.river-parent.river-sea.river-unique.river-outlet.route-points.route-steps.route-links.route-cache.journey-points.journey-steps.marker-cells.burg-cells.burg-positions.burg-features.cell-burgs.state-centers.state-capitals.state-provinces.province-centers.province-capitals.culture-centers.religion-centers.regiment-cells.zone-cells.market-centers.cell-owners.lake-links.cell-arrays.cell-values.feature-data`.split(`.`),fu=[`h`,`t`,`f`,`haven`,`harbor`,`biome`,`pop`,`s`,`culture`,`state`,`province`,`religion`,`burg`,`good`,`r`,`fl`,`conf`,`market`],pu=new class{rules=du;check(){let e=new Map,t=(t,n)=>{let r=e.get(t)??[];r.push(String(n)),e.set(t,r)},{cells:n,features:r}=pack,i=n.i.length,a=e=>Number.isInteger(e)&&e>=0&&e<i,o=e=>a(e)&&!qe(e,pack),s=(e,t)=>e===t||n.c[e]?.includes(t),c=e=>{let t=-1;for(let n=e.length-1;n>=0;n--){let[r,i,o]=e[n];if(!a(o))return!0;let c=S.findCell(r,i);if(!s(o,c)&&!(a(t)&&s(t,c)))return!0;e[n-1]?.[2]!==o&&(t=o)}return!1},l=(e=[])=>e.filter(e=>e.i&&!e.removed),u=(e,t)=>!(!e[t]?.i||e[t].removed),d=e=>a(e)&&r[n.f[e]]?.type===`ocean`,{width:f,height:p}=options.map.graph,m=(e,t)=>e>0&&e<f&&t>0&&t<p,h=new Set(pack.rivers.map(e=>e.i));for(let e of pack.rivers){if(!Array.isArray(e.cells)){t(`river-cells`,e.i);continue}(e.cells.some(e=>e!==-1&&!a(e))||e.points&&e.points.length!==e.cells.length)&&t(`river-cells`,e.i),e.points?.some((t,n)=>a(e.cells[n])&&S.findCell(...t)!==e.cells[n])&&t(`river-points`,e.i),e.cells.some(e=>o(e)&&!h.has(n.r[e]))&&t(`river-ownership`,e.i),(!a(e.source)||!(a(e.mouth)||e.mouth===-1))&&t(`river-ends`,e.i),e.parent&&!h.has(e.parent)&&t(`river-parent`,e.i),e.cells.slice(0,-1).some(d)&&t(`river-sea`,e.i);let r=e.cells.filter((t,n)=>t!==-1&&t!==e.cells[n-1]);new Set(r).size!==r.length&&t(`river-unique`,e.i);let i=e.cells.indexOf(-1),s=e.points?.at(-1);i!==-1&&(i<e.cells.length-1||s&&m(...s))&&t(`river-outlet`,e.i)}let ee=new Set(pack.routes.map(e=>e.i)),te=new Set;for(let e of pack.routes){c(e.points)&&t(`route-points`,e.i);for(let n=1;n<e.points.length;n++){let[r,i]=[e.points[n-1][2],e.points[n][2]];te.add(`${r}-${i}`).add(`${i}-${r}`),a(r)&&a(i)&&!s(r,i)&&t(`route-steps`,e.i)}}for(let[e,r]of Object.entries(n.routes??{}))for(let[n,i]of Object.entries(r))(!a(+e)||!a(+n)||!ee.has(i)||!te.has(`${e}-${n}`))&&t(`route-links`,e);let ne=_.connections;for(let e of ne?.keys()??[])te.has(e)||t(`route-cache`,e);for(let e of pack.journeys??[])for(let n of e.segments){let{points:r}=n;c(r)&&t(`journey-points`,e.i),Ae.getDomain(n.transport)!==`air`&&r.some(([,,e],t)=>t&&a(e)&&!s(r[t-1][2],e))&&t(`journey-steps`,e.i)}for(let e of pack.markers)(!a(e.cell)||S.findCell(e.x,e.y)!==e.cell)&&t(`marker-cells`,e.i);let re=new Set;for(let e of l(pack.burgs)){(!o(e.cell)||n.burg[e.cell]!==e.i||re.has(e.cell))&&t(`burg-cells`,e.i),re.add(e.cell),a(e.cell)&&S.findCell(e.x,e.y)!==e.cell&&t(`burg-positions`,e.i);let i=e.port?r[e.port]:void 0;(e.feature!==n.f[e.cell]||e.port&&(!i||i.land))&&t(`burg-features`,e.i)}for(let e=0;e<i;e++){let r=n.burg[e];r&&(!u(pack.burgs,r)||pack.burgs[r].cell!==e)&&t(`cell-burgs`,e)}for(let e of l(pack.states)){let r=pack.burgs[e.capital];!e.capital||!u(pack.burgs,e.capital)?t(`state-capitals`,e.i):e.center!==r.cell&&t(`state-centers`,e.i),!e.capital&&n.state[e.center]!==e.i&&t(`state-centers`,e.i),e.provinces?.some(e=>!u(pack.provinces,e))&&t(`state-provinces`,e.i);for(let n of e.military??[])a(n.cell)||t(`regiment-cells`,`${e.i}-${n.i}`)}for(let e of l(pack.provinces)){e.burg&&!u(pack.burgs,e.burg)&&t(`province-capitals`,e.i);let r=n.province[e.center]===e.i;(!a(e.center)||!r&&pack.burgs[e.burg]?.cell!==e.center)&&t(`province-centers`,e.i)}for(let e of l(pack.cultures))o(e.center)||t(`culture-centers`,e.i);for(let e of l(pack.religions))o(e.center)||t(`religion-centers`,e.i);for(let e of pack.zones)e.cells.some(e=>!a(e))&&t(`zone-cells`,e.i);for(let e of pack.markets??[])u(pack.burgs,e.centerBurgId)||t(`market-centers`,e.i);let ie=[[n.state,pack.states],[n.culture,pack.cultures],[n.province,pack.provinces],[n.religion,pack.religions]];for(let[e,n]of ie)for(let r=0;r<i;r++)e?.[r]&&!u(n,e[r])&&t(`cell-owners`,r);for(let e of r)e?.type===`lake`&&(e.outlet&&!h.has(e.outlet)||e.inlets?.some(e=>!h.has(e)))&&t(`lake-links`,e.i);for(let e of fu)n[e]?.length!==i&&t(`cell-arrays`,e);for(let e=0;e<i;e++)(!Number.isFinite(n.pop?.[e])||o(e)&&!n.biome?.[e])&&t(`cell-values`,e);for(let e of r)e&&(!e.name||e.type!==`ocean`&&!e.group)&&t(`feature-data`,e.i);return du.flatMap(t=>{let n=e.get(t);return n?[{rule:t,count:n.length,examples:n.slice(0,5)}]:[]})}},mu=new class{smoothHeightmap(){grid.cells.h.forEach((e,t)=>{let n=[e,...grid.cells.c[t].map(e=>grid.cells.h[e])],r=Et(n);grid.cells.h[t]=qe(t,grid)?Math.min(r,19):Math.max(r,20)})}resamplePrimaryGridData(e,t,n,r){grid.cells.h=new Uint8Array(grid.points.length),grid.cells.temp=new Int8Array(grid.points.length),grid.cells.prec=new Uint8Array(grid.points.length);let i=Ge(t.cells.p.map(([e,t],n)=>[e,t,n]));grid.points.forEach(([r,a],o)=>{let[s,c]=n(r,a),l=i.find(s,c,1/0)?.[2];if(l===void 0)return;let u=t.cells.g[l];grid.cells.h[o]=e.cells.h[u],grid.cells.temp[o]=e.cells.temp[u],grid.cells.prec[o]=e.cells.prec[u]}),r>=2&&this.smoothHeightmap()}process(e){let{projection:t,inverse:n,scale:r}=e,i=structuredClone(grid),a=Gn.snapshot();options.map.graph.points=fe(options.generation.graph.density),grid=R.generate(options.map.seed),pack={},this.resamplePrimaryGridData(i,a.pack,n,r),x.markupGrid(),R.addDeepDepressionLakes(),R.openNearSeaLakes(),Pe.calculate(),Vn.generate(),S.generate(),x.markupPack(),Bn.generate(),Ln.createDefaultRuler(),Gn.restore(a,{projection:t,inverse:n,scale:r,rivers:`restore`,relief:!1})}},hu=new class{rename(e){options.map.lore.name=y(e)}setYear(e){if(typeof e!=`number`||!Number.isFinite(e))throw Error(`The year must be a number`);options.map.lore.calendar.year=Math.round(e)}setEra(e,t){let{calendar:n}=options.map.lore;n.era=y(e),n.eraShort=t===void 0?A.getEraShort(n.era):y(t)}setDescription(e){if(typeof e!=`string`)throw Error(`The description must be text`);options.map.lore.description=e}},gu=e=>{let t=new SpeechSynthesisUtterance(e),n=speechSynthesis.getVoices();n.length&&(t.voice=n[Number(options.app.ui.speakerVoice)]??t.voice),speechSynthesis.speak(t)},_u={get pack(){return pack},get grid(){return grid},get options(){return options},get styles(){return styles},...Qe,...Rt,...et,...Ot,...Ke,...wt,...Ut,...i,...De,...ze,...jt,...te,...on,speak:gu,getFileName:_n,VERSION:xn,mapHistory:fn,log:h,fonts:gn,heightmapTemplates:He,precreatedHeightmaps:fs,AddedLabels:In,Biomes:Rn,Burgs:ge,Coastline:ye,Coordinates:Pe,Cultures:de,CustomIcons:Se,Emblems:ie,ErasePipeline:Oi,Features:x,GenerationPipeline:Di,Goods:g,GraphOverride:pn,Grid:R,HeightmapGenerator:zn,Ice:Bn,IconSets:Ee,Icons:Oe,Journeys:Hn,Labels:xe,Lakes:_e,Legends:_t,Lore:hu,MapEntities:le,MapIntegrity:pu,MapRestoration:Gn,Markers:Ei,Markets:rn,Measurers:Ln,Military:ke,Names:A,Notes:mn,Ocean:ct,Options:b,Pack:S,Pins:v,Population:he,Precipitation:st,Production:an,Provinces:tn,Relief:Te,Religions:Ir,Resample:mu,Rivers:we,Routes:_,States:z,Styles:H,Tags:ue,Temperature:Vn,Transports:Ae,Zones:Er,Layers:w,ViewportLayers:ut,TradeAnimation:pt,EmblemRenderer:ft,getLabelsData:mt,fitLegendBox:ot,Controllers:L,Services:B,tip:I,clearMainTip:$t,Dialog:F,zoomTo:Cn,resetZoom:kn,setMapZoom:V,setZoomExtent:jn,setTranslateExtent:Tn,invokeActiveZooming:wn,regenerateMap:jo,regeneratePrompt:Mo,generateMapWithSeed:fr,restoreSeed:mr,showSeedHistoryDialog:pr,applyLayersPreset:Gc,applyURLLayers:Kc,toggleOptions:Rc,hideOptions:Lc,changeCellsDensity:Ls,initiateAutosave:Ui,toggleSaveReminder:qi,copyMapURL:oo,cleanupData:yn,drawCellsValue:(e,t=pack.cells.p)=>ou(e,t),drawPolygons:e=>su(e,grid),drawRouteConnections:()=>cu(pack),drawPoint:lu,drawPath:uu,getVertexPath:e=>pe(e,pack)};Object.defineProperty(window,"FMG",{value:_u}),Za({generate:Ao,regenerateMap:jo,regeneratePrompt:Mo,syncOptionInputs:Es,changeCellsDensity:Ls,openTab:zc,pickMapFile:kc,showExportPane:gc,applyLayersPreset:Gc,applyURLLayers:Kc,mapCommands:il,isLinkable:rl});export{ma as A,Oi as B,wa as C,ta as D,Ra as E,Vi as F,Jn as G,Ci as H,Mi as I,Xn as K,Ni as L,ra as M,zi as N,Sa as O,Li as P,ji as R,Pa as S,Da as T,Ir as U,Ei as V,Er as W,Eo as _,Ul as a,$a as b,ko as boot,Xl as c,nl as d,Pc as f,xo as g,ts as h,pu as i,ka as j,Ea as k,$c as l,fs as m,hu as n,Bl as o,gs as p,qn as q,mu as r,Yl as s,gu as t,el as u,io as v,Ta as w,Xa as x,ro as y,ki as z};