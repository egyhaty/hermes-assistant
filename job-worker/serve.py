"""Authenticated job panel and private remote desktop; no automatic run at startup."""
import asyncio,base64,hashlib,hmac,json,os,signal,subprocess,sys,time,fcntl,secrets
from pathlib import Path
from aiohttp import web,ClientSession,WSMsgType
from worker_guard import validate,profile_digest,profile_ready_error,require_ready
from process_health import clean_stale_display,wait_for_display,failed_children
PROCS=[]
DATA_LOCK=None
PUBLIC='https://hermes.murabba.net'
HTML='''<!doctype html><meta charset="utf-8"><title>Job Applications</title>
<body dir="rtl" style="max-width:800px;margin:50px auto;font:20px sans-serif">
<h1>التقديم على الوظائف</h1><p>عامل مستقل على Kubernetes. لا يبدأ إرسال الطلبات عند التشغيل.</p>
<ol><li><a href="/jobs/desktop/vnc.html?autoconnect=1&resize=scale&path=jobs/desktop/websockify">افتح المتصفح وسجّل دخول LinkedIn</a> حتى تظهر صفحة Feed.</li>
<li><a href="/jobs/panel/">اضبط بياناتك وإجابات التقديم والوظائف المطلوبة</a>. لا تكتب بيانات افتراضية؛ الأسئلة غير المعروفة يتم تخطيها.</li>
<li>ارفع أحدث CV بصيغة PDF:<form method="post" action="/jobs/resume" enctype="multipart/form-data"><input type="file" name="resume" accept="application/pdf" required><button>رفع CV</button></form></li>
<li>بعد اكتمال إعداد بياناتك:<form method="post" action="/jobs/ready"><button>حفظ اكتمال إعداد الملف</button></form></li>
<li>ابدأ وأوقف التقديم من لوحة الوظائف. دورة البحث والتقديم تكمل النتائج المتاحة بدون حد وقت أو عدد؛ التقديم تلقائي بعد اكتمال الملف.</li></ol>
<p>أي CAPTCHA أو تحقق أمني تكمله بنفسك. لا توجد رسائل Recruiters أو طلبات Connections آلية.</p></body>'''
def launch(args):
 # Inherit container logs; do not hide startup failures or dead child processes.
 p=subprocess.Popen(args);PROCS.append(p);return p

def seed():
 global DATA_LOCK
 DATA_LOCK=open('/data/.worker-exclusive.lock','a')
 fcntl.flock(DATA_LOCK.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 clean_stale_display()
 # One worker owns the persistent profile; remove only stale singleton links.
 # No cookies, login data or session files are read or changed here.
 for name in ('SingletonLock','SingletonSocket','SingletonCookie'):
  path=Path('/data/chrome')/name
  if path.is_symlink() or path.exists():path.unlink()
 os.umask(0o077);Path('/data').mkdir(exist_ok=True);Path('/tmp/runtime').mkdir(mode=0o700,exist_ok=True)
 for d in ('logs','all excels','all resumes/default','chrome'):(Path('/data')/d).mkdir(parents=True,exist_ok=True)
 p=Path('/data/user_config.json')
 if not p.exists():
  import app
  c=app._load_defaults()
  for key,v in c.get('personals',{}).items():c['personals'][key]='Decline' if key in ('ethnicity','gender','disability_status','veteran_status') else ''
  c['personals']['first_name']='Karem'
  q=c['questions']
  for k in ('website','linkedIn','us_citizenship','linkedin_headline','linkedin_summary','cover_letter','recent_employer','confidence_level'):q[k]=''
  q.update(years_of_experience='',require_visa='',legally_authorized='',notice_period=None,desired_salary=0,current_ctc=0,default_resume_path='/data/resume.pdf',pause_before_submit=False,pause_at_failed_question=False,user_information_all='Linux, hosting and L3 production operations; CKA. AWS experience is personal projects; Azure is basic labs/theory, without verified Azure production tenure.')
  c['search'].update(search_terms=['DevOps Engineer','Linux System Administrator','Kubernetes Engineer'],search_location='United Arab Emirates',easy_apply_only=True,current_experience=-1,did_masters=False,switch_number=10,pause_after_filters=False)
  c['settings'].update(auto_manage_driver=False,run_in_background=False,stop_before_submit=False,run_non_stop=False,keep_screen_awake=False,follow_companies=False,click_gap=2,safe_mode=False,log_level='WARNING')
  c['secrets'].update(username='username@example.com',password='example_password',use_AI=False,llm_model='nvidia/nemotron-3-ultra-550b-a55b:free',llm_api_key='',llm_api_url='https://openrouter.ai/api/v1')
  facts=Path('/etc/job-profile/profile.json')
  if facts.is_file():
   private=json.loads(facts.read_text())
   for section in ('personals','questions','search'):
    if isinstance(private.get(section),dict):c[section].update(private[section])
  resume=Path('/etc/job-profile/resume.pdf')
  if resume.is_file() and not Path('/data/resume.pdf').exists():Path('/data/resume.pdf').write_bytes(resume.read_bytes())
  p.write_text(json.dumps(c,indent=2))

def check_password(request):
 try:
  raw=request.headers.get('Authorization','')
  if not raw.startswith('Basic ') or len(raw)>2048:return False
  u,p=base64.b64decode(raw[6:],validate=True).decode().split(':',1)
  fields=os.environ['PASSWORD_HASH'].split('$')
  if fields[:4]!=['scrypt','16384','8','1']:return False
  actual=hashlib.scrypt(p.encode(),salt=base64.b64decode(fields[4]),n=16384,r=8,p=1,dklen=32)
  return hmac.compare_digest(u,os.environ['USERNAME']) and hmac.compare_digest(actual,base64.b64decode(fields[5]))
 except Exception:return False
LOGIN_HTML='<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>دخول لوحة الوظائف</title><body style="max-width:440px;margin:80px auto;font:20px sans-serif"><h1>لوحة تقديم الوظائف</h1><p>ادخل بنفس اسم المستخدم وكلمة مرور لوحة هرمز.</p><form method="post" action="/jobs/login"><label>اسم المستخدم<input name="username" value="karem" autocomplete="username" required></label><br><label>كلمة المرور<input name="password" type="password" autocomplete="current-password" required></label><br><button>دخول</button></form><p>بيانات دخول LinkedIn تُكتب داخل المتصفح البعيد بعد الدخول هنا.</p></body></html>'
ATTEMPTS={}
SESSIONS={}
def has_session(request):
 token=request.cookies.get('jobs_session','')
 expires=SESSIONS.get(token,0)
 return bool(expires>time.time())
@web.middleware
async def auth(request,handler):
 if request.path=='/health':
  failed=failed_children(PROCS)
  if failed:return web.json_response({'browser_ready':False,'failed_children':failed},status=503)
  try:
   async with request.app['client'].get('http://127.0.0.1:9222/json/version',timeout=2) as response:ok=response.status==200
   async with request.app['client'].get('http://127.0.0.1:5000/api/status',timeout=2) as response:ok=ok and response.status==200
  except Exception:ok=False
  return web.json_response({'browser_ready':ok},status=200 if ok else 503)
 token=request.headers.get('Authorization','')
 if request.path in ('/control/status','/control/start','/control/stop','/control/scheduled-start','/control/schedule-check'):
  if not hmac.compare_digest(token,'Bearer '+os.environ['CONTROL_TOKEN']):raise web.HTTPUnauthorized()
 else:
  if not request.path.startswith('/jobs/'):raise web.HTTPNotFound()
  if request.method not in ('GET','HEAD') and request.headers.get('Origin')!=PUBLIC:raise web.HTTPForbidden(text='Origin check failed')
  if request.path=='/jobs/login':return await handler(request)
  if request.headers.get('Upgrade','').lower()=='websocket' and request.headers.get('Origin')!=PUBLIC:raise web.HTTPForbidden()
  if not has_session(request):
   if request.path=='/jobs/panel/api/run':print('Jobs Start rejected: missing or expired web session',flush=True)
   if request.method=='GET' and '/api/' not in request.path and request.headers.get('Upgrade','').lower()!='websocket':raise web.HTTPSeeOther('/jobs/login')
   raise web.HTTPUnauthorized()
 if request.method=='POST' and request.path in ('/control/start','/control/scheduled-start','/control/schedule-check','/jobs/panel/api/run'):
  if failed_children(PROCS):raise web.HTTPServiceUnavailable(text='Worker services unavailable; recovery pending')
  async with request.app['start_lock']:return await handler(request)
 return await handler(request)

async def handle(request):
 if request.path in ('/control/scheduled-start','/control/schedule-check'):
  if request.method!='POST':raise web.HTTPMethodNotAllowed(request.method,['POST'])
  async with request.app['client'].get('http://127.0.0.1:5000/api/status',timeout=10) as r:status=await r.json()
  if status.get('running'):return web.json_response({**status,'skipped':True,'reason':'A run is already active; browser left untouched.'})
  error=profile_ready_error()
  if error:return web.json_response({'error':error},status=409)
  from scheduled_start import prepare_feed
  try:await asyncio.to_thread(prepare_feed)
  except Exception:return web.json_response({'error':'Could not prepare LinkedIn Feed; no run started.'},status=503)
  error=require_ready()
  if error:return web.json_response({'error':error},status=409)
  if request.path.endswith('schedule-check'):return web.json_response({'ready':True,'started':False})
  async with request.app['client'].post('http://127.0.0.1:5000/api/run',timeout=15) as r:
   return web.json_response(await r.json(),status=r.status)
 if request.path=='/jobs/login':
  if request.method=='GET':
   if has_session(request):raise web.HTTPSeeOther('/jobs/')
   return web.Response(text=LOGIN_HTML,content_type='text/html',headers={'Cache-Control':'no-store'})
  if request.method!='POST':raise web.HTTPMethodNotAllowed(request.method,['GET','POST'])
  peer=request.remote;now=time.monotonic();history=[x for x in ATTEMPTS.get(peer,[]) if now-x<60]
  if len(history)>=20:raise web.HTTPTooManyRequests()
  form=await request.post();u=str(form.get('username',''));p=str(form.get('password',''))
  if len(u)+len(p)>1024:raise web.HTTPBadRequest()
  import types
  check=types.SimpleNamespace(headers={'Authorization':'Basic '+base64.b64encode((u+':'+p).encode()).decode()})
  if not await asyncio.to_thread(check_password,check):
   ATTEMPTS[peer]=history+[now]
   return web.Response(text=LOGIN_HTML.replace('<h1>','<p>بيانات الدخول غير صحيحة.</p><h1>',1),content_type='text/html',status=401,headers={'Cache-Control':'no-store'})
  session=secrets.token_urlsafe(32)
  for key,expiry in list(SESSIONS.items()):
   if expiry<time.time():SESSIONS.pop(key,None)
  SESSIONS[session]=time.time()+21600
  response=web.HTTPSeeOther('/jobs/');response.set_cookie('jobs_session',session,max_age=21600,path='/jobs/',secure=True,httponly=True,samesite='Strict');return response
 if request.path=='/jobs/logout' and request.method=='POST':
  SESSIONS.pop(request.cookies.get('jobs_session',''),None);response=web.HTTPSeeOther('/jobs/login');response.del_cookie('jobs_session',path='/jobs/');return response
 if request.path=='/jobs/':return web.Response(text=HTML,content_type='text/html')
 if request.path=='/jobs/resume' and request.method=='POST':
  reader=await request.multipart();part=await reader.next()
  if part is None or part.name!='resume':raise web.HTTPBadRequest()
  data=await part.read()
  if len(data)>10*1024*1024 or not data.startswith(b'%PDF-'):raise web.HTTPBadRequest(text='PDF up to 10 MB required')
  p=Path('/data/resume.pdf');p.write_bytes(data);p.chmod(0o600)
  raise web.HTTPSeeOther('/jobs/')
 if request.path=='/jobs/ready' and request.method=='POST':
  error=validate()
  if error:raise web.HTTPBadRequest(text=error)
  Path('/data/profile-ready').write_text(profile_digest());raise web.HTTPSeeOther('/jobs/panel/')
 if request.path.startswith('/control/'):
  target={'/control/status':'/api/status','/control/start':'/api/run','/control/stop':'/api/stop'}[request.path]
  expected='GET' if request.path.endswith('/status') else 'POST'
  if request.method!=expected:raise web.HTTPMethodNotAllowed(request.method,[expected])
  base='http://127.0.0.1:5000'
 elif request.path.startswith('/jobs/panel/'):
  target=request.path.removeprefix('/jobs/panel')
  if target.startswith('/api/update'):raise web.HTTPForbidden(text='Immutable installation; updates run through CI')
  base='http://127.0.0.1:5000'
 elif request.path.startswith('/jobs/desktop/'):
  target='/'+request.path.removeprefix('/jobs/desktop/');base='http://127.0.0.1:6080'
 else:raise web.HTTPNotFound()
 if request.query_string:target+='?'+request.query_string
 headers={k:v for k,v in request.headers.items() if k.lower() not in ('authorization','host','connection','upgrade','content-length','cookie','origin')}
 session=request.app['client']
 if request.headers.get('Upgrade','').lower()=='websocket':
  async with session.ws_connect(base+target) as upstream:
   ws=web.WebSocketResponse();await ws.prepare(request)
   async def relay(src,dst):
    async for message in src:
     if message.type==WSMsgType.BINARY:await dst.send_bytes(message.data)
     elif message.type==WSMsgType.TEXT:await dst.send_str(message.data)
     else:break
   tasks=[asyncio.create_task(relay(ws,upstream)),asyncio.create_task(relay(upstream,ws))]
   done,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
   for task in pending:task.cancel()
   return ws
 async with session.request(request.method,base+target,headers=headers,data=await request.read(),allow_redirects=False) as response:
  if request.path=='/jobs/panel/api/run':print('Jobs Start backend HTTP '+str(response.status),flush=True)
  body=await response.read();out={k:v for k,v in response.headers.items() if k.lower() not in ('content-length','transfer-encoding','connection','content-encoding','access-control-allow-origin')}
  if 'Location' in out and out['Location'].startswith('/'):out['Location']='/jobs/panel'+out['Location']
  return web.Response(body=body,status=response.status,headers=out)
async def watch_children():
 while True:
  failed=failed_children(PROCS)
  if failed:
   print('Critical worker child exited; health checks will trigger recovery: '+json.dumps(failed),flush=True)
   return
  await asyncio.sleep(2)
async def start(app):
 app['client']=ClientSession();app['start_lock']=asyncio.Lock()
 app['process_monitor']=asyncio.create_task(watch_children())
async def cleanup(app):
 app['process_monitor'].cancel()
 try:await app['process_monitor']
 except asyncio.CancelledError:pass
 await app['client'].close()
 for proc in reversed(PROCS):
  if proc.poll() is None:proc.terminate()
 for proc in reversed(PROCS):
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill()

def main():
 for name in ('USERNAME','PASSWORD_HASH','CONTROL_TOKEN'):
  if not os.environ.get(name):raise SystemExit('Missing required worker authentication')
 seed()
 if os.environ.get('JOB_AI_PROVIDER')=='groq' and os.environ.get('GROQ_API_KEY'):
  # Preserve the approval of verified personal facts when changing only AI routing.
  config=Path('/data/user_config.json');marker=Path('/data/profile-ready')
  armed=marker.exists() and marker.read_text()==profile_digest()
  c=json.loads(config.read_text());c['secrets'].update(ai_provider='openai',llm_model='openai/gpt-oss-120b',llm_api_url='https://api.groq.com/openai/v1',llm_api_key='',use_AI=True)
  config.write_text(json.dumps(c,indent=2))
  if armed:marker.write_text(profile_digest())
 # Xlib requires an authority file, and every GUI child inherits this cookie.
 authority=Path('/data/.Xauthority');authority.touch(mode=0o600,exist_ok=True);authority.chmod(0o600)
 os.environ['XAUTHORITY']=str(authority)
 subprocess.run(['xauth','-f',str(authority),'add',':99','MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 display=launch(['Xvfb',':99','-screen','0','1440x900x24','-nolisten','tcp','-auth',str(authority)])
 wait_for_display(display)
 launch(['chromium','--user-data-dir=/data/chrome','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9222','--no-first-run','--no-default-browser-check','--disable-dev-shm-usage','https://www.linkedin.com/login'])
 launch(['x11vnc','-display',':99','-localhost','-forever','-shared','-nopw','-rfbport','5900'])
 launch(['websockify','--web=/usr/share/novnc','127.0.0.1:6080','127.0.0.1:5900'])
 launch(['gunicorn','--bind','127.0.0.1:5000','--workers','1','--threads','4','--chdir','/data','app:app'])
 app=web.Application(middlewares=[auth],client_max_size=12*1024*1024);app.router.add_route('*','/{path:.*}',handle);app.on_startup.append(start);app.on_cleanup.append(cleanup)
 web.run_app(app,host='0.0.0.0',port=9118,print=None,access_log=None)
if __name__=='__main__':main()
