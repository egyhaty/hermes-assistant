"""One-time truthful profile configuration gate; never a per-application approval."""
import hashlib,json
from pathlib import Path
CONFIG=Path('/data/user_config.json')
def profile_digest():
 return hashlib.sha256(CONFIG.read_bytes()+Path('/data/resume.pdf').read_bytes()).hexdigest()
def validate():
 try:c=json.loads(CONFIG.read_text())
 except Exception:return 'Save your application profile first.'
 required={'personals':['first_name','last_name','phone_number','current_city'], 'questions':['years_of_experience','require_visa','legally_authorized','notice_period']}
 for section,keys in required.items():
  for key in keys:
   if c.get(section,{}).get(key) in (None,''):return 'Missing verified profile field: '+key
 for k in ('require_visa','legally_authorized'):
  if c['questions'][k] not in ('Yes','No'):return 'Set work authorization and sponsorship answers explicitly.'
 if not Path('/data/resume.pdf').is_file() or not Path('/data/resume.pdf').read_bytes().startswith(b'%PDF-'):return 'Upload your current PDF resume.'
 sec=c.get('secrets',{})
 if sec.get('use_AI') and not str(sec.get('llm_model','')).endswith(':free'):return 'Only an explicitly free OpenRouter model is allowed.'
 if c.get('search',{}).get('easy_apply_only') is not True:return 'Only Easy Apply is enabled for this worker.'
 return None
def require_ready():
 error=validate()
 if error:return error
 try:ready=Path('/data/profile-ready').read_text()
 except OSError:return 'Complete the profile setup on /jobs/ before the first automatic run.'
 return None if ready==profile_digest() else 'Profile changed: complete profile setup again before running.'
