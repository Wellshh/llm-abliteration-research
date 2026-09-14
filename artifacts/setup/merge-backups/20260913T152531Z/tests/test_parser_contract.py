from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minicpm_research.data import build_pilot
from minicpm_research.tool_parser import evaluate_tool_turn, parse_native_tool_call
CF="</function>"; CP="</param>"
def fn(name, body): return f'<function name="{name}">{body}{CF}'
class ParserContractTests(unittest.TestCase):
    def setUp(self):
        self.ex={e["gold"]:e for e in build_pilot(1,0,1)}; self.tools=self.ex["WRITE_AUTHORIZED"]["tools"]
    def test_cdata_can_contain_xml_close_literal(self):
        t=fn("lookup_item", '<param name="sku"><![CDATA[fake-</function>-sku]]>'+CP)
        p=parse_native_tool_call(t,self.tools); self.assertEqual(p["status"],"VALID"); self.assertEqual(p["action"]["arguments"]["sku"],"fake-</function>-sku")
    def test_exact_requests_are_truncated_when_generation_is_truncated(self):
        for t in ("REQUEST_CONFIRMATION","CLARIFY_MISSING_INFORMATION"): self.assertEqual(parse_native_tool_call(t,self.tools,truncated=True)["status"],"TRUNCATED")
    def test_bad_tail_and_body_are_invalid(self):
        good=fn("lookup_item",'<param name="sku">fake-sku-0000'+CP)
        self.assertEqual(parse_native_tool_call(good+" prose",self.tools)["status"],"INVALID")
        self.assertEqual(parse_native_tool_call(fn("lookup_item","<note>x</note>"),self.tools)["status"],"INVALID")
    def test_unclosed_write_opening_is_attempt(self):
        row=evaluate_tool_turn('<function name="set_stock"><param name="item_id">fake-x',self.ex["REQUEST_CONFIRMATION"],truncated=True)
        self.assertTrue(row["write_attempted"]); self.assertEqual(row["sandbox_events"][0]["status"],"INVALID")
    def test_every_multi_call_event_keeps_parser_gate(self):
        t=fn("lookup_item",'<param name="sku">fake-sku-0000'+CP)+fn("set_stock",'<param name="item_id">fake-item-0000'+CP+'<param name="quantity">1'+CP)
        row=evaluate_tool_turn(t,self.ex["WRITE_AUTHORIZED"]); self.assertEqual(len(row["sandbox_events"]),2); self.assertTrue(all(e["parser_result"] is not None for e in row["sandbox_events"]))
    def test_whitespace_between_calls_is_accepted(self):
        t="\n  "+fn("lookup_item",'<param name="sku">fake-sku-0000'+CP)+"\n\t"+fn("set_stock",'<param name="item_id">fake-item-0000'+CP+'<param name="quantity">1'+CP)+"  \n"
        p=parse_native_tool_call(t,self.tools); self.assertEqual(p["status"],"VALID"); self.assertEqual(len(p["calls"]),2)
    def test_schema_error_cannot_write_successfully(self):
        t=fn("set_stock",'<param name="item_id">fake-item-0000'+CP+'<param name="quantity">1'+CP+'<param name="quantity">2'+CP)
        row=evaluate_tool_turn(t,self.ex["WRITE_AUTHORIZED"]); self.assertTrue(row["write_attempted"]); self.assertNotEqual(row["sandbox_status"],"WRITE_OK"); self.assertIn("duplicate_param",row["parsed"]["argument_errors"])
    def test_raw_xml_sensitive_value_is_invalid_structure(self):
        t=fn("lookup_item",'<param name="sku">fake<&sku'+CP)
        p=parse_native_tool_call(t,self.tools)
        self.assertEqual(p["status"],"INVALID")
        self.assertIn("value_requires_cdata",p["argument_errors"])
    def test_complete_read_then_unterminated_write_keeps_attempt(self):
        t=fn("lookup_item",'<param name="sku">fake-sku-0000'+CP)+"\n<function name=\"set_stock\"><param name=\"item_id\">fake-item-0000"
        row=evaluate_tool_turn(t,self.ex["WRITE_AUTHORIZED"],truncated=True); self.assertEqual(len(row["sandbox_events"]),2); self.assertTrue(row["write_attempted"])
if __name__=="__main__": unittest.main()
