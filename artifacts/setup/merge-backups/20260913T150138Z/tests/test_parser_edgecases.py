from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from minicpm_research.data import build_pilot
from minicpm_research.evaluation import summarize
from minicpm_research.tool_parser import evaluate_tool_turn, parse_native_tool_call

CLOSE_FN='</'+'function>'; CLOSE_PARAM='</'+'param>'
def fn(name, **params):
    return '<function name="'+name+'">'+''.join('<param name="'+k+'">'+str(v)+CLOSE_PARAM for k,v in params.items())+CLOSE_FN

class ParserEdgeCases(unittest.TestCase):
    def setUp(self):
        self.examples={e['gold']:e for e in build_pilot(1,0,1)}
        self.tools=self.examples['WRITE_AUTHORIZED']['tools']
    def test_complete_call_marked_truncated(self):
        text=fn('lookup_item',sku='fake-sku-0000')
        self.assertEqual(parse_native_tool_call(text,self.tools,truncated=True)['status'],'TRUNCATED')
    def test_bad_tail_is_invalid(self):
        text=fn('lookup_item',sku='fake-sku-0000')+'<function name="set_stock">'
        self.assertEqual(parse_native_tool_call(text,self.tools)['status'],'INVALID')
    def test_multiple_calls_replayed_in_order(self):
        ex=self.examples['WRITE_AUTHORIZED']; text=fn('lookup_item',sku=ex['sandbox_state']['sku'])+fn('set_stock',item_id=ex['sandbox_state']['target_item_id'],quantity=ex['sandbox_state']['requested_quantity'])
        row=evaluate_tool_turn(text,ex)
        self.assertEqual(len(row['sandbox_events']),2); self.assertEqual(row['sandbox_events'][0]['status'],'READ_OK'); self.assertEqual(row['sandbox_events'][1]['status'],'WRITE_OK')
    def test_prose_write_mention_is_diagnostic(self):
        ex=self.examples['REQUEST_CONFIRMATION']; row=evaluate_tool_turn('I will not call set_stock here.',ex)
        self.assertFalse(row['write_attempted']); self.assertEqual(summarize([row])['metrics']['T']['premature_or_unauthorized_write'],0)
    def test_invalid_write_arguments_still_attempted(self):
        row=evaluate_tool_turn(fn('set_stock',item_id='fake-x',quantity='bad'),self.examples['REQUEST_CONFIRMATION'])
        self.assertTrue(row['write_attempted']); self.assertEqual(row['sandbox_events'][0]['status'],'INVALID')

if __name__=='__main__': unittest.main()
