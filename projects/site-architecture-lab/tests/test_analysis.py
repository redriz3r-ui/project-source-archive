import copy
import json
import tempfile
import unittest
from pathlib import Path
from site_architecture_lab.analysis import analyze, endpoint
from site_architecture_lab.reports import generate

ROOT=Path(__file__).resolve().parents[1]
class AnalysisTests(unittest.TestCase):
 def setUp(self): self.har=json.loads((ROOT/'examples/synthetic.har').read_text())
 def test_valid_and_categories(self):
  d=analyze(self.har,True)
  self.assertEqual(d['summary']['total_requests'],14)
  self.assertEqual(d['summary']['unique_hosts'],5)
  self.assertEqual({r['kind'] for r in d['requests']},{'document','frontend','api','realtime','media'})
  self.assertTrue(d['synthetic'])
 def test_malformed(self):
  for value in [None,[],{}, {'log':{}},{'log':{'entries':[{}]}}, {'log':{'entries':'bad'}}]:
   with self.subTest(value=value),self.assertRaises(ValueError): analyze(value)
 def test_api(self):
  d=analyze(self.har)
  self.assertEqual(d['requests'][4]['kind'],'api')
  self.assertEqual(d['requests'][0]['kind'],'document')
 def test_websocket_sse_polling(self):
  d=analyze(self.har)
  self.assertEqual(d['summary']['websocket_handshakes'],1)
  self.assertEqual(d['requests'][7]['realtime'],'SSE')
  self.assertIn('inferred',d['requests'][12]['realtime'])
  h=copy.deepcopy(self.har);h['log']['entries'][6]['response']['status']=200
  self.assertEqual(analyze(h)['summary']['websocket_handshakes'],0)
 def test_streaming(self):
  p=analyze(self.har)['summary']['protocols']
  for expected in ['HLS','MPEG-DASH','Transport segment','Fragmented media','WebRTC indicator (inferred)']:self.assertIn(expected,p)
 def test_privacy_all_outputs(self):
  h=copy.deepcopy(self.har); e=h['log']['entries'][0]
  e['request'].update(url='https://USERNAME:PASSWORD@alice.example.test/private/SECRET/person@example.com?token=QUERYSECRET',headers=[{'name':'Cookie','value':'COOKIESECRET'},{'name':'Authorization','value':'AUTHSECRET'}],postData={'text':'BODYSECRET'})
  e['response']['content']['text']='RESPONSESECRET'
  e['response']['headers'] += [{'name':'Server','value':'SERVERSECRET'},{'name':'Cache-Control','value':'private, EVILSECRET'},{'name':'Content-Security-Policy','value':'CSPSECRET'}]
  e['_initiator']={'type':'script','url':'STACKSECRET'}
  e['response']['content']['mimeType']='application/TYPESECRET'
  d=analyze(h)
  with tempfile.TemporaryDirectory() as directory:
   generate(d,directory)
   output=''.join(p.read_text() for p in Path(directory).iterdir())
   for secret in ['USERNAME','PASSWORD','alice','SECRET','person@','QUERYSECRET','COOKIESECRET','AUTHSECRET','BODYSECRET','RESPONSESECRET','SERVERSECRET','EVILSECRET','CSPSECRET','STACKSECRET','TYPESECRET']:
    self.assertNotIn(secret,output)
 def test_normalization(self):
  self.assertEqual(endpoint('https://a.example.test/api/12345?secret=yes'),('[subdomain].example.test','/api/[redacted]'))
  self.assertNotIn('john',endpoint('https://john.example.test/john%40mail.test')[1])
 def test_reports(self):
  with tempfile.TemporaryDirectory() as directory:
   generate(analyze(self.har,True),directory)
   self.assertEqual(len(list(Path(directory).iterdir())),5)
   text=(Path(directory)/'architecture.md').read_text()
   for label in ['OBSERVED','INFERRED','UNKNOWN','SYNTHETIC','R1']:self.assertIn(label,text)
 def test_empty(self):
  d=analyze({'log':{'entries':[]}})
  self.assertEqual(d['summary']['average_duration_ms'],0)
 def test_bad_numbers(self):
  e=self.har['log']['entries'][0];e['time']=float('nan');e['response']['bodySize']=-1;e['startedDateTime']='bad'
  d=analyze(self.har)
  json.dumps(d,allow_nan=False)
  self.assertEqual(d['requests'][0]['duration_ms'],0)
  self.assertIsNone(d['requests'][0]['start_ms'])
if __name__=='__main__':unittest.main()
