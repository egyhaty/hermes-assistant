"""One-time truthful profile configuration gate; never a per-application approval."""
import hashlib,json,urllib.request,urllib.parse,os
from pathlib import Path
DATA=Path(os.environ.get('JOB_DATA', '/data'))
CONFIG=DATA/'user_config.json'
def profile_digest():
 return hashlib.sha256(CONFIG.read_bytes()+(DATA/'resume.pdf').read_bytes()).hexdigest()
def validate():
 try:c=json.loads(CONFIG.read_text())
 except Exception:return 'Save your application profile first.'
 required={'personals':['first_name','last_name','phone_number','current_city'], 'questions':['years_of_experience','require_visa','notice_period']}
 for section,keys in required.items():
  for key in keys:
   if c.get(section,{}).get(key) in (None,''):return 'Missing verified profile field: '+key
 for k in ('require_visa','legally_authorized'):
  if c['questions'].get(k) not in ('Yes','No',None,''):return 'Use explicit Yes/No or leave an unknown authorization answer blank.'
 if not (DATA/'resume.pdf').is_file() or not (DATA/'resume.pdf').read_bytes().startswith(b'%PDF-'):return 'Upload your current PDF resume.'
 sec=c.get('secrets',{})
 if sec.get('use_AI'):
  provider=os.environ.get('JOB_AI_PROVIDER','openrouter')
  if provider=='groq':
   if sec.get('llm_model')!='openai/gpt-oss-120b':return 'Only the configured Groq free-plan model is enabled.'
   if not os.environ.get('GROQ_API_KEY'):return 'Add the dedicated Groq free-plan API Secret first.'
  elif provider!='openrouter' or not str(sec.get('llm_model','')).endswith(':free'):return 'Only an explicitly free OpenRouter model is allowed.'
 if c.get('search',{}).get('easy_apply_only') is not True:return 'Only Easy Apply is enabled for this worker.'
 return None
def require_ready():
 error=validate()
 if error:return error
 try:ready=(DATA/'profile-ready').read_text()
 except OSError:return 'Complete the profile setup on /jobs/ before the first automatic run.'
 if ready!=profile_digest():return 'Profile changed: review your saved profile at /jobs/ and click Complete profile setup, then return here and Start.'
 try:
  with urllib.request.urlopen('http://127.0.0.1:9222/json',timeout=3) as r:pages=json.load(r)
  logged_in=any(urllib.parse.urlsplit(x.get('url','')).hostname=='www.linkedin.com' and urllib.parse.urlsplit(x.get('url','')).path.startswith('/feed') for x in pages)
 except Exception:logged_in=False
 return None if logged_in else 'Open the remote browser and sign in to LinkedIn until the Feed page appears.'
