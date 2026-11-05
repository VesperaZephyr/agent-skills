import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/index_records.py'
spec=importlib.util.spec_from_file_location('index_records',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class IndexRecordsTest(unittest.TestCase):
 def invoke(self,left,right=None):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);a=base/'a.idx';a.write_text(left,encoding='utf-8');out=base/'out.json';args=[sys.executable,str(SCRIPT),str(a),'--out',str(out)]
   if right is not None:
    b=base/'b.idx';b.write_text(right,encoding='utf-8');args+=['--compare',str(b)]
   result=subprocess.run(args,capture_output=True)
   return result.returncode,json.loads(out.read_text(encoding='utf-8'))
 def test_nested_and_quoted_separators(self):
  rows,errors=m.parse(r'\indexentry[main]{a"!b@{A!B}!c@C|hyperpage}{12}')
  self.assertFalse(errors);self.assertEqual(len(rows[0]['levels']),2);self.assertEqual(rows[0]['levels'][0]['sort'],r'a"!b');self.assertEqual(rows[0]['levels'][0]['display'],'{A!B}');self.assertEqual(rows[0]['encap'],'hyperpage')
 def test_equal_count_page_drift(self):
  rc,report=self.invoke(r'\indexentry{x}{12}',r'\indexentry{x}{13}')
  self.assertEqual(rc,1);self.assertFalse(report['converged']);self.assertEqual(report['removed'][0]['page'],'12');self.assertEqual(report['added'][0]['page'],'13')
 def test_duplicate_multiplicity(self):
  entry=r'\indexentry{x}{12}'
  rc,report=self.invoke(entry+'\n'+entry,entry)
  self.assertEqual(rc,1);self.assertEqual(report['removed'][0]['count'],1)
 def test_order_only_is_equal(self):
  a=r'\indexentry{x}{12}';b=r'\indexentry{y}{13}'
  rc,report=self.invoke(a+'\n'+b,b+'\n'+a);self.assertEqual(rc,0);self.assertTrue(report['converged'])
 def test_errors_are_not_clean(self):
  for text in [r'\indexentry{x}{12',r'\custom{x}',r'\indexentry{a@b@c}{1}']:
   with self.subTest(text=text):
    rc,report=self.invoke(text);self.assertEqual(rc,1);self.assertTrue(report['errors'])
 def test_conflicts_and_index_namespaces(self):
  text='\n'.join([r'\indexentry[main]{a@A!b@B}{1}',r'\indexentry[main]{aa@A!b@B}{2}',r'\indexentry[main]{a@Other}{3}',r'\indexentry[sym]{z@A}{4}'])
  rc,report=self.invoke(text);self.assertEqual(rc,0)
  self.assertIn('display_path_conflict',{c['kind'] for c in report['candidates']});self.assertIn('sort_path_conflict',{c['kind'] for c in report['candidates']});self.assertTrue(all(c['index']=='main' for c in report['candidates']));self.assertEqual(report['semantic_review'],'not_performed')
if __name__=='__main__':unittest.main()
