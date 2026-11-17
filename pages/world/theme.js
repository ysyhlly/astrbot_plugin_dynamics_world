/* Shares Chat Dynamics' local preference, independent of the host data-theme. */
(() => {
  const key='chat_dynamics_ui',valid=value=>value==='day'||value==='night';
  let saved;try{saved=localStorage.getItem(key);}catch{}
  const query=new URLSearchParams(location.search).get('ui');
  const paint=value=>{
    const mode=valid(value)?value:'day';
    document.documentElement.dataset.uiTheme=mode;
    document.documentElement.style.colorScheme=mode==='night'?'dark':'light';
    const button=document.getElementById('dwTheme');
    if(button){button.setAttribute('aria-pressed',String(mode==='night'));button.setAttribute('aria-label',mode==='night'?'切换到日间模式':'切换到夜间模式');button.querySelector('.dw-theme-label').textContent=mode==='night'?'夜间模式':'日间模式';}
  };
  const rememberUrl=mode=>{try{const url=new URL(location.href);url.searchParams.set('ui',mode);history.replaceState(history.state,'',url);}catch{}};
  paint(valid(query)?query:saved);
  document.addEventListener('DOMContentLoaded',()=>{
    paint(document.documentElement.dataset.uiTheme);
    document.getElementById('dwTheme').addEventListener('click',()=>{
      const mode=document.documentElement.dataset.uiTheme==='night'?'day':'night';paint(mode);
      let stored=true;try{localStorage.setItem(key,mode);}catch{stored=false;}
      rememberUrl(mode);
      document.getElementById('dwThemeStatus').textContent=stored?'':'当前页已切换，浏览器未允许保存偏好。';
    });
  });
  window.addEventListener('storage',event=>{if(event.key===key&&valid(event.newValue)){paint(event.newValue);rememberUrl(event.newValue);}});
})();
