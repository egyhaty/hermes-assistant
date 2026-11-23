"""Private, deduplicated mail reports; never starts or modifies applications."""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import smtplib
import socket
import sqlite3
import ssl
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from application_journal import Journal
from job_reports import dubai_time, safe_cell

DUBAI = ZoneInfo('Asia/Dubai')
STATUS = {'confirmed':'تقديم مؤكّد من الموقع','skipped':'مستبعد / لم يتم التقديم','needs_input':'يحتاج إجابات أو تدخل منك','uncertain':'محاولة غير مؤكدة - لا يعاد إرسالها','attempting':'محاولة قيد التنفيذ','eligible':'مرشح للتقديم، لم يرسل بعد','already_applied':'متقدم له بالفعل'}
REPORTS = 'https://hermes.murabba.net/jobs/reports/'


def address(value):
    if not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',value or ''):
        raise ValueError('A configured report email address is required')
    return value


def link(url, label):
    parsed = urllib.parse.urlsplit(str(url))
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password: return escape(label)
    return '<a href="'+escape(str(url),quote=True)+'">'+escape(label)+'</a>'


def fields(row):
    job = row['job']; meta = job.get('resume_tailoring', {}); screen = job.get('screening', {})
    return [dubai_time(row['updated']), row['source'], job.get('track','devops_uae'), job.get('company',''), job.get('title',''),
            job.get('location',''), STATUS.get(row['status'],row['status']), row['status'], row['attempts'], row['reason'],
            '; '.join(screen.get('gaps',[])), '; '.join(screen.get('required_unknown',[])), bool(screen.get('stretch')),
            meta.get('delivery','profile_cv'), meta.get('artifact',''), row.get('cv_sha256',''),
            job.get('screening_audit',{}).get('reason',''), row['url']]


def build_message(records, runs, state, recipient, sender, now=None):
    recipient, sender = address(recipient), address(sender)
    now = now or datetime.now(DUBAI)
    now = now.astimezone(DUBAI)
    day = now.date(); daily = [r for r in records if datetime.fromtimestamp(r['updated'],DUBAI).date()==day]
    daily_counts, totals = Counter(r['status'] for r in daily), Counter(r['status'] for r in records)
    mode = 'قيد التشغيل - تقرير مرحلي' if state.get('running') else 'انتهى التشغيل / آخر حالة متاحة'
    text = '\n'.join(['تقرير Hermes للتقديمات',now.strftime('%Y-%m-%d %H:%M')+' - توقيت دبي',mode,
        'تقديمات مؤكدة مسجلة اليوم: '+str(daily_counts['confirmed']),
        'الإجمالي التاريخي للتقديمات المؤكدة: '+str(totals['confirmed']),
        'سجلات تحتاج تدخل اليوم: '+str(daily_counts['needs_input']),
        'كل الوظائف والأسباب والمهارات الناقصة ونسخة السي في موجودة في التقرير المرفق.',
        'التجهيز أو الاستبعاد أو مجرد الضغط على Apply ليس تقديمًا مكتملًا.',REPORTS])
    parts=['<html><body dir="rtl" style="font:15px Arial,sans-serif;color:#172b43;line-height:1.8"><h1>تقرير Hermes للتقديمات</h1>',
           '<p>'+escape(now.strftime('%Y-%m-%d %H:%M'))+' - توقيت دبي<br>'+escape(mode)+'</p>',
           '<h2>اليوم مقابل الإجمالي التاريخي</h2><table border="1" cellpadding="8" cellspacing="0"><tr><th>الحالة</th><th>سجلات اليوم</th><th>الإجمالي</th></tr>']
    for status in ['confirmed','needs_input','uncertain','attempting','eligible','skipped']:
        parts.append('<tr><td>'+STATUS[status]+'</td><td>'+str(daily_counts[status])+'</td><td>'+str(totals[status])+'</td></tr>')
    parts.extend(['</table><p>أرقام اليوم تعتمد على تاريخ تحديث سجل الوظيفة بتوقيت دبي. إعادة تقييم إعلان قديم ليست تقديمًا جديدًا. العدد المؤكد يشمل فقط ما أكد الموقع استلامه.</p>',
                  '<p>التقديم الموسع يسمح بوجود فجوات خبرة؛ لا يضيفها للسي في كخبرة مكتسبة. LinkedIn يدعم نسخة مخصصة داخل الطلب، والمسارات الأخرى تستخدم سي في البروفايل ما لم يذكر خلاف ذلك.</p>',
                  '<h2>التشغيل الحالي / الأخير</h2><p>'+escape(str(state.get('stop_reason') or ('الدورة مستمرة' if state.get('running') else 'لا توجد نتيجة تشغيل نهائية متاحة')) )+'</p>'])
    parts.append('<p>بدء المرحلة المسجلة: '+escape(dubai_time(state.get('started_at')))+'<br>آخر نهاية مسجلة: '+escape(dubai_time(state.get('finished_at')) )+'</p>')
    for source in state.get('sources',[]):
        parts.append('<p><b>'+escape(str(source.get('source','')))+' / '+escape(str(source.get('track','')) )+'</b>: '+escape(str(source.get('reason','')) )+'</p>')
    parts.append('<h2>تفاصيل الوظائف المسجلة اليوم</h2>')
    for row in daily:
        job=row['job']; meta=job.get('resume_tailoring',{}); screen=job.get('screening',{})
        parts.append('<div style="border:1px solid #d7dfe7;padding:12px;margin:12px 0"><h3>'+escape(job.get('title','بدون مسمى'))+' — '+escape(job.get('company',''))+'</h3>')
        for label,value in [('الموقع',row['source']),('المكان',job.get('location','')),('الحالة',STATUS.get(row['status'],row['status'])),('آخر تحديث',dubai_time(row['updated'])),('عدد المحاولات',str(row['attempts'])),('السبب',row['reason']),('فجوات الخبرة','; '.join(screen.get('gaps',[]))),('المطلوب منك','; '.join(screen.get('required_unknown',[]))),('حالة السي في',meta.get('delivery','profile_cv'))]:
            if value:parts.append('<p><b>'+escape(label)+':</b> '+escape(str(value))+'</p>')
        if screen.get('stretch'):parts.append('<p>فرصة أعلى من المطابقة الموثقة؛ السي في والإجابات يظلان من الحقائق المعتمدة.</p>')
        artifact=meta.get('artifact','')
        if re.fullmatch(r'[a-f0-9]{64}/resume\.pdf',artifact):parts.append('<p>'+link(REPORTS+'cv?id='+artifact.split('/')[0],'تنزيل نسخة السي في المرتبطة بالوظيفة (يتطلب تسجيل دخول Hermes)')+'</p>')
        proof=job.get('proof','')
        if re.fullmatch(r'[a-z0-9-]+\.png',proof):parts.append('<p>'+link('https://hermes.murabba.net/jobs/proof/'+proof,'دليل حالة التقديم (يتطلب تسجيل دخول)')+'</p>')
        audit=job.get('screening_audit',{})
        if audit.get('verified_fit') is False:parts.append('<p><b>تنبيه مراجعة المطابقة:</b> '+escape(audit.get('reason','لا تعتبر هذه الوظيفة مطابقة مؤكدة'))+'</p>')
        parts.append('<p>'+link(row['url'],'فتح إعلان الوظيفة')+'</p></div>')
    if not daily:parts.append('<p>لا توجد سجلات محدثة اليوم.</p>')
    parts.append('<h2>آخر دورات التشغيل</h2>')
    for run in runs[:10]:
        parts.append('<p>'+escape(dubai_time(run['started']))+' | '+escape(run['status'])+' | '+escape(run['engine'])+' | '+escape(run['reason'])+'</p>')
    parts.append('<p>المرفق يحتوي جميع السجلات التاريخية، بما فيها المستبعدة. لا توجد كلمات مرور أو جلسات متصفح في التقرير. '+link(REPORTS,'فتح التقارير الكاملة')+'</p></body></html>')
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['Updated Dubai','Source','Track','Company','Role','Location','Status Arabic','Status','Attempts','Reason','Skill gaps','Missing answers','Stretch application','CV delivery','CV artifact','CV SHA256','Fit audit','Job URL'])
    for row in records:writer.writerow([safe_cell(v) for v in fields(row)])
    msg=EmailMessage();msg['From']=sender;msg['To']=recipient;msg['Subject']='Hermes Jobs | '+now.strftime('%Y-%m-%d %H:%M')+' Dubai | '+str(daily_counts['confirmed'])+' confirmed today'
    msg['Date']=format_datetime(now);msg['Message-ID']=make_msgid(domain='gmail.com')
    msg.set_content(text);msg.add_alternative(''.join(parts),subtype='html')
    msg.add_attachment(('\ufeff'+out.getvalue()).encode('utf-8'),maintype='text',subtype='csv',filename='hermes-applications-'+day.isoformat()+'.csv')
    return msg


def send_report(data, state, delivery_id, smtp_factory=smtplib.SMTP):
    data=Path(data);recipient=address(os.environ.get('JOB_REPORT_TO',''));sender=address(os.environ.get('JOB_SMTP_USER',''))
    password=os.environ.get('JOB_SMTP_PASSWORD','')
    if not password:raise ValueError('Email report credentials are not configured')
    journal=Journal(data/'job-applications.sqlite3')
    with journal.connect() as db:
        db.row_factory=sqlite3.Row
        records=[dict(r,job=json.loads(r['job'])) for r in db.execute('SELECT * FROM applications ORDER BY updated DESC')]
    msg=build_message(records,journal.run_history(),state,recipient,sender)
    with sqlite3.connect(data/'email-report-delivery.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY,status TEXT,message_id TEXT,updated INTEGER,error TEXT)')
        try:db.execute('INSERT INTO deliveries VALUES (?,?,?,?,?)',(delivery_id,'preparing',msg['Message-ID'],int(time.time()),''))
        except sqlite3.IntegrityError:return {'status':'already_processed','delivery_id':delivery_id}
    stage='preparing'
    try:
        with smtp_factory(os.environ.get('JOB_SMTP_HOST','smtp.gmail.com'),587,timeout=30) as smtp:
            smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo();smtp.login(sender,password)
            with sqlite3.connect(data/'email-report-delivery.sqlite3') as db:db.execute('UPDATE deliveries SET status="sending",updated=? WHERE id=?',(int(time.time()),delivery_id))
            stage='sending'
            refused=smtp.send_message(msg)
            if refused:raise smtplib.SMTPRecipientsRefused(refused)
            stage='accepted'
    except Exception as error:
        status='accepted' if stage=='accepted' else 'uncertain' if stage=='sending' else 'failed'
        with sqlite3.connect(data/'email-report-delivery.sqlite3') as db:db.execute('UPDATE deliveries SET status=?,updated=?,error=? WHERE id=?',(status,int(time.time()),type(error).__name__,delivery_id))
        return {'status':status,'error_type':type(error).__name__,'delivery_id':delivery_id}
    with sqlite3.connect(data/'email-report-delivery.sqlite3') as db:db.execute('UPDATE deliveries SET status="accepted",updated=? WHERE id=?',(int(time.time()),delivery_id))
    return {'status':'accepted','delivery_id':delivery_id,'recipient':recipient,'message_id':msg['Message-ID']}


def main(snapshot=False):
    data=Path(os.environ.get('JOB_DATA','/data'))
    request=urllib.request.Request(os.environ.get('JOB_CONTROL_URL','http://hermes-jobs.hermes.svc.cluster.local/control/status'),headers={'Authorization':'Bearer '+os.environ['CONTROL_TOKEN']})
    state=json.load(urllib.request.urlopen(request,timeout=20))
    if not snapshot and state.get('running'):return {'status':'deferred','reason':'Application cycle still running'}
    run=state.get('run_id')
    if not snapshot and not state.get('finished_at'):return {'status':'deferred','reason':'No completed cycle available'}
    if not run:return {'status':'deferred','reason':'No run identity available'}
    delivery_id=('snapshot-'+datetime.now(DUBAI).strftime('%Y%m%d-%H%M') if snapshot else 'run-'+run)
    return send_report(data,state,delivery_id)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',action='store_true');p.add_argument('--dispatch',action='store_true');args=p.parse_args()
    try:result=main(snapshot=args.snapshot)
    except Exception as error:result={'status':'failed','error_type':type(error).__name__}
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status'] in ('accepted','deferred','already_processed') else 1)
