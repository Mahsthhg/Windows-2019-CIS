<?php
/**
 * includes/ai_widget.php — دستیار هوش مصنوعی شناور (معلم/ادمین)
 * در صفحات پنل include می‌شود. به config/ai.php و توابع h()/isAdmin() نیاز دارد.
 */
require_once __DIR__ . '/../config/ai.php';
$AI_ROLE   = isAdmin() ? 'admin' : 'teacher';
$AI_CSRF   = generateCsrfToken();
$AI_TITLE  = $AI_ROLE === 'admin' ? 'دستیار فنی ادمین' : 'دستیار پشتیبانی';
?>
<style>
#aiFab{position:fixed;bottom:22px;left:22px;z-index:9000;width:60px;height:60px;border-radius:50%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:none;cursor:pointer;
  box-shadow:0 10px 30px rgba(99,102,241,.45);font-size:26px;display:flex;align-items:center;justify-content:center;transition:.25s;}
#aiFab:hover{transform:scale(1.08);}
#aiPanel{position:fixed;bottom:92px;left:22px;z-index:9001;width:380px;max-width:calc(100vw - 32px);height:540px;max-height:calc(100vh - 130px);
  background:#fff;border-radius:22px;box-shadow:0 24px 60px rgba(0,0,0,.3);display:none;flex-direction:column;overflow:hidden;
  font-family:'Vazirmatn',sans-serif;border:1px solid #e2e8f0;}
#aiPanel.open{display:flex;animation:aiUp .25s ease;}
@keyframes aiUp{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:translateY(0);}}
.ai-head{background:linear-gradient(135deg,#1e1b4b,#0f172a);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px;}
.ai-head .ai-ic{font-size:22px;}
.ai-head h4{font-size:15px;font-weight:800;flex:1;}
.ai-head button{background:rgba(255,255,255,.15);border:none;color:#fff;width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:16px;}
.ai-body{flex:1;overflow-y:auto;padding:14px;background:#f8fafc;display:flex;flex-direction:column;gap:10px;}
.ai-msg{max-width:85%;padding:10px 13px;border-radius:16px;font-size:13px;line-height:1.8;white-space:pre-wrap;word-break:break-word;}
.ai-msg.user{align-self:flex-start;background:#6366f1;color:#fff;border-bottom-right-radius:4px;}
.ai-msg.bot{align-self:flex-end;background:#fff;color:#0f172a;border:1px solid #e2e8f0;border-bottom-left-radius:4px;}
.ai-msg pre{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:10px;overflow-x:auto;font-size:11px;direction:ltr;text-align:left;margin:6px 0;}
.ai-msg.err{background:#fee2e2;color:#991b1b;align-self:center;font-size:12px;}
.ai-typing{align-self:flex-end;color:#64748b;font-size:12px;}
.ai-foot{border-top:1px solid #e2e8f0;padding:10px;background:#fff;}
.ai-tools{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;}
.ai-chip{font-size:11px;background:#ede9fe;color:#5b21b6;border:none;border-radius:20px;padding:5px 10px;cursor:pointer;font-family:inherit;}
.ai-inrow{display:flex;gap:8px;align-items:flex-end;}
.ai-inrow textarea{flex:1;border:2px solid #e2e8f0;border-radius:14px;padding:9px 12px;font-family:inherit;font-size:13px;resize:none;max-height:90px;}
.ai-inrow textarea:focus{outline:none;border-color:#6366f1;}
.ai-send{background:#6366f1;color:#fff;border:none;border-radius:12px;width:42px;height:42px;cursor:pointer;font-size:18px;flex-shrink:0;}
.ai-diag{display:none;background:#f1f5f9;border-radius:14px;padding:10px;margin-bottom:8px;}
.ai-diag.open{display:block;}
.ai-diag input,.ai-diag textarea{width:100%;border:1.5px solid #cbd5e1;border-radius:10px;padding:7px 10px;font-family:inherit;font-size:12px;margin-bottom:6px;}
.ai-diag button{background:#0ea5e9;color:#fff;border:none;border-radius:10px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;}
@media(max-width:480px){#aiPanel{height:70vh;}}
</style>

<button id="aiFab" onclick="aiToggle()" title="<?= h($AI_TITLE) ?>">🤖</button>
<div id="aiPanel" aria-live="polite">
  <div class="ai-head">
    <span class="ai-ic">🤖</span>
    <h4><?= h($AI_TITLE) ?></h4>
    <button onclick="aiToggle()" aria-label="بستن">✕</button>
  </div>
  <div class="ai-body" id="aiBody">
    <div class="ai-msg bot">سلام! 👋 من دستیار هوش مصنوعی هستم. <?= $AI_ROLE === 'admin' ? 'برای عیب‌یابی، سوال فنی یا بررسی فایل از من بپرس.' : 'هر سوالی دربارهٔ کار با سامانه داری بپرس.' ?></div>
  </div>
  <div class="ai-foot">
    <?php if ($AI_ROLE === 'admin'): ?>
    <div class="ai-tools">
      <button class="ai-chip" onclick="aiDiagToggle()">🔧 عیب‌یابی فایل</button>
      <button class="ai-chip" onclick="aiQuick('چطور امنیت سایت را بیشتر کنم؟')">🛡️ امنیت</button>
    </div>
    <div class="ai-diag" id="aiDiag">
      <input type="text" id="aiDiagFile" placeholder="مسیر فایل (مثال: exam/index.php یا api/submit_exam.php)">
      <textarea id="aiDiagDesc" rows="2" placeholder="شرح مشکل (اختیاری)"></textarea>
      <button onclick="aiDiagnose()">تحلیل و پیشنهاد اصلاح</button>
    </div>
    <?php else: ?>
    <div class="ai-tools">
      <button class="ai-chip" onclick="aiQuick('چطور یک آزمون جدید بسازم؟')">📝 ساخت آزمون</button>
      <button class="ai-chip" onclick="aiQuick('ضدتقلب و وب‌کم را چطور فعال کنم؟')">🛡️ ضدتقلب</button>
      <button class="ai-chip" onclick="aiQuick('چطور نتایج را خروجی اکسل بگیرم؟')">📊 نتایج</button>
    </div>
    <?php endif; ?>
    <div class="ai-inrow">
      <textarea id="aiInput" rows="1" placeholder="سوال خود را بنویسید..." onkeydown="aiKey(event)"></textarea>
      <button class="ai-send" onclick="aiSend()">➤</button>
    </div>
  </div>
</div>

<script>
const AI_CSRF = '<?= h($AI_CSRF) ?>';
const AI_ENDPOINT = '../api/ai_assist.php';
let aiHistory = [];
let aiBusy = false;

function aiToggle(){ document.getElementById('aiPanel').classList.toggle('open'); }
function aiDiagToggle(){ document.getElementById('aiDiag').classList.toggle('open'); }
function aiKey(e){ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); aiSend(); } }
function aiQuick(t){ document.getElementById('aiInput').value=t; aiSend(); }

function aiEscape(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function aiFormat(s){
  // بلوک‌های کد و **bold** سادهٔ
  let parts = s.split(/```[a-zA-Z]*\n?/);
  let html='', code=false;
  for(const p of parts){
    if(code) html += '<pre>'+aiEscape(p)+'</pre>';
    else html += aiEscape(p).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
    code=!code;
  }
  return html;
}
function aiAdd(role, text, isErr){
  const b=document.getElementById('aiBody');
  const d=document.createElement('div');
  d.className='ai-msg '+(isErr?'err':(role==='user'?'user':'bot'));
  d.innerHTML = isErr ? aiEscape(text) : aiFormat(text);
  b.appendChild(d); b.scrollTop=b.scrollHeight;
}
function aiTyping(on){
  let t=document.getElementById('aiTyping');
  if(on && !t){ const b=document.getElementById('aiBody'); t=document.createElement('div'); t.id='aiTyping'; t.className='ai-typing'; t.textContent='در حال نوشتن…'; b.appendChild(t); b.scrollTop=b.scrollHeight; }
  else if(!on && t){ t.remove(); }
}

async function aiCall(payload){
  payload.csrf_token = AI_CSRF;
  const r = await fetch(AI_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  return r.json();
}

async function aiSend(){
  if(aiBusy) return;
  const inp=document.getElementById('aiInput');
  const text=inp.value.trim();
  if(!text) return;
  inp.value=''; inp.style.height='auto';
  aiAdd('user', text);
  aiHistory.push({role:'user',content:text});
  aiBusy=true; aiTyping(true);
  try{
    const d = await aiCall({action:'chat', messages:aiHistory});
    aiTyping(false);
    if(d.ok){ aiAdd('bot', d.text); aiHistory.push({role:'assistant',content:d.text}); }
    else aiAdd('bot', d.error||'خطای نامشخص', true);
  }catch(e){ aiTyping(false); aiAdd('bot','خطای شبکه',true); }
  aiBusy=false;
}

async function aiDiagnose(){
  if(aiBusy) return;
  const file=document.getElementById('aiDiagFile').value.trim();
  const desc=document.getElementById('aiDiagDesc').value.trim();
  if(!file){ alert('مسیر فایل را وارد کنید'); return; }
  aiAdd('user','🔧 تحلیل فایل: '+file+(desc?('\nمشکل: '+desc):''));
  aiBusy=true; aiTyping(true);
  try{
    const d = await aiCall({action:'diagnose', file:file, description:desc});
    aiTyping(false);
    if(d.ok) aiAdd('bot', d.text);
    else aiAdd('bot', d.error||'خطا', true);
  }catch(e){ aiTyping(false); aiAdd('bot','خطای شبکه',true); }
  aiBusy=false;
}

// رشد خودکار ارتفاع textarea
document.getElementById('aiInput').addEventListener('input',function(){ this.style.height='auto'; this.style.height=Math.min(this.scrollHeight,90)+'px'; });
</script>
