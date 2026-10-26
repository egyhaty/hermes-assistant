#!/usr/bin/env python3
"""Local bilingual report generation. No remote resources or credential files are read."""
import argparse,html,io,json,os,subprocess,tempfile,unicodedata
from pathlib import Path
from urllib.parse import unquote,urlsplit
FONT_ROOT=Path('/usr/share/fonts').resolve()
CSS='''@page {size:A4; margin:20mm 17mm 20mm; @bottom-center {direction:ltr;unicode-bidi:isolate;content:counter(page) " / " counter(pages); font:10pt "DejaVu Sans";color:#64748b;}}
[dir="ltr"] {text-align:left;} [dir="rtl"] {text-align:right;}
body {font-family:"Noto Naskh Arabic","DejaVu Sans",sans-serif;font-size:12pt;line-height:1.65;color:#172b4d;}
h1 {font-size:25pt;line-height:1.4;color:#102f50;margin:0 0 4mm;border-bottom:3pt solid #159a9c;padding-bottom:4mm;}
h2 {font-size:17pt;line-height:1.4;color:#123e63;margin:7mm 0 3mm;break-after:avoid;}
p {margin:2mm 0;orphans:3;widows:3;} .subtitle {color:#64748b;font-size:11pt;margin-bottom:6mm;}
table {width:100%;border-collapse:collapse;margin:4mm 0;font-size:10pt;table-layout:fixed;} thead {display:table-header-group;}
th {background:#123e63;color:white;} th,td {padding:2.5mm;border:0.5pt solid #d8e2ec;overflow-wrap:anywhere;vertical-align:top;}
tr {break-inside:avoid;} tbody tr:nth-child(even){background:#f0f6fa;} ul {padding-inline-start:6mm;} li {margin:2mm 0;}
.new-page {break-before:page;} .ltr {direction:ltr;unicode-bidi:isolate;} img {max-width:100%;}
'''
def escape(value):return html.escape(str(value),quote=True)
def text_dir(value):
 for char in str(value):
  bidi=unicodedata.bidirectional(char)
  if bidi in ('R','AL'):return 'rtl'
  if bidi=='L':return 'ltr'
 return 'rtl'
def document(data):
 if not isinstance(data,dict) or not isinstance(data.get('title'),str):raise ValueError('Report needs a title string.')
 direction=data.get('direction','rtl')
 if direction not in ('rtl','ltr'):raise ValueError('direction must be rtl or ltr')
 parts=['<!doctype html><html lang="ar" dir="'+direction+'"><meta charset="utf-8"><title>'+escape(data['title'])+'</title><body><h1>'+escape(data['title'])+'</h1>']
 if data.get('subtitle'):parts.append('<p class="subtitle" dir="'+text_dir(data['subtitle'])+'">'+escape(data['subtitle'])+'</p>')
 for section in data.get('sections',[]):
  parts.append('<section'+(' class="new-page"' if section.get('new_page') else '')+'>')
  if section.get('heading'):parts.append('<h2 dir="'+text_dir(section['heading'])+'">'+escape(section['heading'])+'</h2>')
  for paragraph in section.get('paragraphs',[]):parts.append('<p dir="'+text_dir(paragraph)+'">'+escape(paragraph)+'</p>')
  if section.get('bullets'):parts.append('<ul>'+''.join('<li dir="'+text_dir(x)+'">'+escape(x)+'</li>' for x in section['bullets'])+'</ul>')
  table=section.get('table')
  if table:
   headers=table['headers'];rows=table['rows']
   if any(len(row)!=len(headers) for row in rows):raise ValueError('Every table row must match its headers.')
   parts.append('<table dir="'+text_dir(headers[0] if headers else '')+'"><thead><tr>'+''.join('<th dir="'+text_dir(x)+'">'+escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>')
   for row in rows:parts.append('<tr>'+''.join('<td dir="'+text_dir(x)+'">'+escape(x)+'</td>' for x in row)+'</tr>')
   parts.append('</tbody></table>')
  parts.append('</section>')
 return ''.join(parts)+'</body></html>'
def fetcher(asset_root):
 asset_root=Path(asset_root).resolve() if asset_root else None
 def local_only(url,*args,**kwargs):
  from weasyprint import default_url_fetcher
  parsed=urlsplit(url)
  if parsed.scheme=='data':return default_url_fetcher(url)
  if parsed.scheme=='file' and not parsed.netloc:
   path=Path(unquote(parsed.path)).resolve()
   if path.is_relative_to(FONT_ROOT) or (asset_root and path.is_relative_to(asset_root)):
    return default_url_fetcher(path.as_uri())
  raise ValueError('PDF resource blocked: only local fonts and report assets are allowed.')
 return local_only

def sample():
 return {'title':'اختبار التقارير العربية والإنجليزية','subtitle':'Hermes PDF readiness - 2026-10-27','sections':[
 {'heading':'ملخص التحقق','paragraphs':['هذا تقرير تجريبي ببيانات وهمية للتحقق من اتصال الحروف العربية واتجاه النص وصحة إنشاء ملف PDF.','Mixed Arabic / English: بيئة Kubernetes وLinux جاهزة لتوليد التقارير محليًا دون إرسال محتواها إلى خدمة خارجية.'],
 'table':{'headers':['الأولوية','الفحص','النتيجة'],'rows':[['عالية','اتجاه العربية وتشكيل الحروف','اختبار مرئي مطلوب'],['متوسطة','PDF generation / fonts','Local renderer and embedded fonts'],['عادية','الصفحات والجداول','ترقيم تلقائي ورؤوس أعمدة واضحة']]},
 'bullets':['الملف تجريبي، وليس التقرير السابق الذي طلبته من هرمز.','لا توجد بيانات شخصية أو مفاتيح في هذا المستند.']},
 {'heading':'Technical verification','new_page':True,'paragraphs':['English text remains readable from left to right. Arabic sections retain their natural reading direction.','يمكن استخدام الجداول والعناوين والنقاط لإعداد تقارير تحليلية عربية وإنجليزية.'],
 'table':{'headers':['Component','Purpose'],'rows':[['WeasyPrint + Pango','Arabic shaping and HTML layout'],['ReportLab','Programmatic PDF creation'],['Poppler + pypdf','Rendering and structural verification']]}}]}
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--self-test',action='store_true');parser.add_argument('--preview',action='store_true');parser.add_argument('--overwrite',action='store_true');args=parser.parse_args()
 from weasyprint import HTML,CSS as Style
 from weasyprint.text.fonts import FontConfiguration
 from pypdf import PdfReader
 if args.output.is_symlink():raise SystemExit('Refusing a symlink output.')
 if args.output.exists() and not args.overwrite:raise SystemExit('Output already exists; choose a new filename or use --overwrite.')
 if args.self_test:content=document(sample());base=Path('/tmp');assets=None
 else:
  if not args.input:parser.error('--input or --self-test is required')
  source=args.input.resolve();base=source.parent;assets=(base/'assets').resolve()
  raw=source.read_text(encoding='utf-8');content=document(json.loads(raw)) if source.suffix.lower()=='.json' else raw
 fonts=FontConfiguration();payload=HTML(string=content,base_url=str(base),url_fetcher=fetcher(assets)).write_pdf(stylesheets=[Style(string=CSS,font_config=fonts)],font_config=fonts)
 pages=len(PdfReader(io.BytesIO(payload)).pages)
 if not payload.startswith(b'%PDF-') or not pages:raise SystemExit('No valid PDF generated.')
 out=args.output.absolute();out.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.pdf-',dir=out.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(payload)
  os.replace(tmp,out)
 finally:
  if Path(tmp).exists():Path(tmp).unlink()
 result={'pdf':str(out),'pages':pages,'bytes':len(payload)}
 if args.preview:
  preview=out.with_suffix('.png');subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1400','-png',str(out),str(preview.with_suffix(''))],check=True);result['preview']=str(preview)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
