"""Build demo/index.html: the published Artifact source + a browser-only stand-in for window.claude.
The stand-in keeps data in localStorage and syncs open tabs, so a participant tab and a wizard tab
can talk to each other on GitHub Pages without claude.ai."""
import json, sys
REPO = sys.argv[1] if len(sys.argv) > 1 else "."
app = open(f'{REPO}/src/act-connect.html').read()
cfg = json.load(open(f'{REPO}/data/sample-config.json'))
pool = json.load(open(f'{REPO}/data/sample-pool.json'))
seed = {'config/script': cfg['script'], 'config/practice': cfg['practice'], 'config/settings': cfg['settings']}
for k, v in pool.items(): seed['pool/' + k] = v

RUNTIME = r'''(function(){
'use strict';
var KEY = 'actconnect-demo-v1';
var SEED = __SEED__;
var WIZARD_PIN = '0827';
var OWNER = false, me = null;
var roleResolve; var roleReady = new Promise(function(res){ roleResolve = res; });
function finishRole(wizard){
  OWNER = wizard; me = wizard ? 'demo-researcher' : 'demo-participant';
  var gate = document.getElementById('roleGate'); if (gate) gate.remove();
  roleResolve();
}
window.ActConnectChooseRole = function(wantWizard){
  if (!wantWizard) { finishRole(false); return; }
  var ok = false; try { ok = sessionStorage.getItem('actconnect-wizard-pin') === WIZARD_PIN; } catch (e) {}
  if (!ok) { var entered = window.prompt('연구자 PIN을 입력하세요'); ok = entered === WIZARD_PIN; if (ok) { try { sessionStorage.setItem('actconnect-wizard-pin', entered); } catch (e) {} } }
  if (ok) finishRole(true); else { alert('PIN이 올바르지 않습니다. 참여자 화면으로 진행합니다.'); finishRole(false); }
};
var store = new Map();
function load(){ store.clear(); var raw = null; try { raw = localStorage.getItem(KEY); } catch (e) {}
  var obj = raw ? JSON.parse(raw) : JSON.parse(JSON.stringify(SEED)); for (var k in obj) store.set(k, obj[k]); if (!raw) save(); }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(Object.fromEntries(store))); } catch (e) {} }
load();
var subs = new Set();
function notify(){ subs.forEach(function(f){ try { f(); } catch (e) { console.error(e); } }); }
window.addEventListener('storage', function(e){ if (e.key === KEY) { load(); notify(); } });
function clone(v){ return v == null ? v : JSON.parse(JSON.stringify(v)); }
function snapDoc(path){ var d = store.get(path); return { id: path.split('/').pop(), exists: !!d, data: function(){ return clone(d); }, metadata: {} }; }
function commit(){ save(); notify(); }
function docRef(path){ return { id: path.split('/').pop(), path: path,
  get: async function(){ return snapDoc(path); },
  set: async function(d){ store.set(path, clone(d)); commit(); },
  update: async function(d){ if (!store.has(path)) throw { code: 'not_found', message: 'no doc' }; store.set(path, Object.assign({}, store.get(path), clone(d))); commit(); },
  delete: async function(){ store.delete(path); commit(); },
  onSnapshot: function(next){ var prev; var f = function(){ var s = snapDoc(path); var j = JSON.stringify(s.data()); if (j !== prev) { prev = j; next(s); } }; subs.add(f); setTimeout(f, 0); return function(){ subs.delete(f); }; },
  collection: function(c){ return colRef(path + '/' + c); } }; }
function colRef(path, filters, ord, lim){ filters = filters || []; var q = { path: path,
  doc: function(id){ return docRef(path + '/' + (id || Math.random().toString(36).slice(2))); },
  where: function(f, op, v){ return colRef(path, filters.concat([[f, op, v]]), ord, lim); },
  orderBy: function(f, d){ return colRef(path, filters, [f, d || 'asc'], lim); },
  limit: function(n){ return colRef(path, filters, ord, n); },
  _docs: function(){ var depth = path.split('/').length + 1;
    var ds = Array.from(store.keys()).filter(function(k){ return k.indexOf(path + '/') === 0 && k.split('/').length === depth; }).map(snapDoc);
    ds = ds.filter(function(d){ return filters.every(function(x){ return x[1] === '==' ? d.data()[x[0]] === x[2] : true; }); });
    if (ord) ds.sort(function(a, b){ return (a.data()[ord[0]] > b.data()[ord[0]] ? 1 : -1) * (ord[1] === 'desc' ? -1 : 1); });
    if (lim) ds = ds.slice(0, lim); return ds; },
  get: async function(){ var docs = q._docs(); return { docs: docs, size: docs.length, empty: !docs.length }; },
  onSnapshot: function(next){ var prevMap = new Map(), ran = false; var f = function(){ var docs = q._docs(); var m = new Map(docs.map(function(d){ return [d.id, JSON.stringify(d.data())]; })); var ch = [];
      docs.forEach(function(d){ if (!prevMap.has(d.id)) ch.push({ type: 'added', doc: d }); else if (prevMap.get(d.id) !== m.get(d.id)) ch.push({ type: 'modified', doc: d }); });
      prevMap.forEach(function(_, id){ if (!m.has(id)) ch.push({ type: 'removed', doc: { id: id, exists: true, data: function(){ return {}; } } }); });
      if (ch.length || !ran) { ran = true; prevMap = m; next({ docs: docs, size: docs.length, empty: !docs.length, docChanges: function(){ return ch; }, metadata: {} }); } };
    subs.add(f); setTimeout(f, 0); return function(){ subs.delete(f); }; } };
  return q; }
var db = { doc: docRef, collection: function(p){ return colRef(p); } };
var user = { isOwner: async function(){ await roleReady; return OWNER; }, canEdit: async function(){ return true; }, can: async function(){ return null; },
  id: async function(){ await roleReady; return me; }, me: async function(){ await roleReady; return { id: me, name: '', email: null }; } };
var downloads = { save: async function(r){ var blob = new Blob([r.data], { type: 'text/plain;charset=utf-8' }); var a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = r.filename; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 1000); return { status: 'saved' }; } };
window.claude = { use: async function(n){ return ({ db: db, user: user, downloads: downloads })[n] || null; } };
window.ActConnectDemo = { reset: function(){ try { localStorage.removeItem(KEY); } catch (e) {} location.reload(); } };
})();'''.replace('__SEED__', json.dumps(seed, ensure_ascii=False))

BAR = '''<style>
#demoBar{height:30px;display:flex;align-items:center;gap:12px;padding:0 16px;font:12px/1 "IBM Plex Sans KR",system-ui,sans-serif;background:#1e2226;color:#e6e8ea}
#demoBar b{font-weight:600}#demoBar a,#demoBar button{color:#9cc3e6;background:none;border:0;padding:0;font:inherit;cursor:pointer;text-decoration:underline}
#demoBar .sp{flex:1}#demoBar .muted{color:#a5adb5}
body #root{height:calc(100% - 30px)}
@media (max-width:640px){#demoBar .muted{display:none}}
#roleGate{position:fixed;inset:0;background:#15181b;color:#e6e8ea;display:flex;align-items:center;justify-content:center;z-index:9999;font:14px/1.5 "IBM Plex Sans KR",system-ui,sans-serif;text-align:center}
#roleGate h2{margin:0 0 8px;font-size:18px;font-weight:600}
#roleGate p{margin:0 0 20px;color:#a5adb5}
#roleGate .choices{display:flex;gap:10px;justify-content:center}
#roleGate button{padding:10px 20px;border-radius:6px;border:1px solid #3a4046;background:#262b30;color:#e6e8ea;cursor:pointer;font:inherit}
#roleGate button:hover{background:#2f353b}
</style>
<div id="roleGate"><div><h2>Act &amp; Connect 데모</h2><p>참여자이신가요, 연구자이신가요?</p>
<div class="choices"><button type="button" onclick="ActConnectChooseRole(false)">참여자</button><button type="button" onclick="ActConnectChooseRole(true)">연구자</button></div></div></div>
<div id="demoBar" role="note"><b>Act &amp; Connect 데모</b><span class="muted">claude.ai 없이 이 브라우저에서만 동작합니다.</span><span class="sp"></span>
<button type="button" onclick="if(confirm('데모 데이터를 모두 지우고 처음 상태로 돌립니다.'))ActConnectDemo.reset()">초기화</button></div>
'''

html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="description" content="Act & Connect Phase 1 프로토타입 데모 — 배우의 캐릭터 해석 지원 연구">'
        '<style>*,*::before,*::after{box-sizing:border-box}html,body{margin:0}</style></head><body>'
        + BAR + '<script>' + RUNTIME + '</script>\n' + app + '\n</body></html>\n')
html = html.replace('<title>Act &amp; Connect</title>', '<title>Act &amp; Connect · 데모</title>', 1)
open(f'{REPO}/demo/index.html', 'w').write(html)
print('demo built', len(html))
