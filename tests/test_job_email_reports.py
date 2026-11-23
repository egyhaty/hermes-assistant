import os,sys,tempfile,unittest,json,sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from application_journal import Journal
from email_reports import build_message,send_report,address,DUBAI
class Mail:
 calls=0;fail=False
 def __init__(self,*a,**kw):pass
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def ehlo(self):pass
 def starttls(self,**kw):pass
 def login(self,*a):pass
 def send_message(self,msg):
  Mail.calls+=1
  if Mail.fail:raise TimeoutError()
  return {}
class MailTests(unittest.TestCase):
 def record(self):return {'updated':datetime(2026,11,24,8,tzinfo=DUBAI).timestamp(),'source':'linkedin','url':'https://www.linkedin.com/jobs/view/123/','status':'needs_input','reason':'Salary missing <script>','attempts':1,'cv_sha256':'a'*64,'job':{'title':'DevOps <script>alert(1)</script>','company':'Test','screening':{'gaps':['AWS labs only'],'required_unknown':['Salary']}}}
 def test_clear_counts_escape_and_complete_attachment(self):
  now=datetime(2026,11,24,9,tzinfo=DUBAI);r=self.record();old=dict(r,status='confirmed',updated=1)
  msg=build_message([r,old],[],{'running':True},'owner@example.com','sender@example.com',now)
  self.assertIn('0 confirmed today',msg['Subject']);body=msg.get_body(preferencelist=('html',)).get_content()
  self.assertNotIn('<script>',body);self.assertIn('&lt;script&gt;',body);self.assertIn('AWS labs only',body)
  attachments=list(msg.iter_attachments());self.assertEqual(len(attachments),1)
  self.assertIn('Salary',attachments[0].get_payload(decode=True).decode('utf-8'))
  self.assertNotIn('متقدم له بالفعل',msg['Subject'])
 def test_header_injection_rejected(self):
  with self.assertRaises(ValueError):address('a@example.com\nBcc: b@example.com')
 def test_dedup_and_smtp_uncertainty_never_auto_retries(self):
  for fail in [False,True]:
   with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'JOB_REPORT_TO':'owner@example.com','JOB_SMTP_USER':'sender@example.com','JOB_SMTP_PASSWORD':'fake-test-only'}):
    Mail.calls=0;Mail.fail=fail;Journal(Path(tmp)/'job-applications.sqlite3')
    first=send_report(tmp,{},'run-test',Mail);second=send_report(tmp,{},'run-test',Mail)
    self.assertEqual(first['status'],'uncertain' if fail else 'accepted');self.assertEqual(second['status'],'already_processed');self.assertEqual(Mail.calls,1)
    saved=sqlite3.connect(Path(tmp)/'email-report-delivery.sqlite3').execute('SELECT error FROM deliveries').fetchone()[0]
    self.assertNotIn('fake-test-only',saved)

class ReportMountTests(unittest.TestCase):
 def test_reporter_reads_exact_worker_data_subdirectory(self):
  root=Path(__file__).resolve().parents[1]
  worker=next(x for x in json.loads((root/'deploy/jobs.json').read_text())['items'] if x['kind']=='Deployment' and x['metadata']['name']=='hermes-jobs')
  report=next(x for x in json.loads((root/'deploy/jobs-reports.json').read_text())['items'] if x['kind']=='CronJob')
  original=next(m for m in worker['spec']['template']['spec']['containers'][0]['volumeMounts'] if m['name']=='data')
  actual=next(m for m in report['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['volumeMounts'] if m['name']=='data')
  self.assertEqual(actual,original)
