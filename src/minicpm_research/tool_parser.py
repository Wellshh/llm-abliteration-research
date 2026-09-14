"""Bounded parser and deterministic replay for pinned MiniCPM5 XML tools."""
from __future__ import annotations
import html, re
from typing import Any, Mapping, Sequence
from .sandbox import Sandbox

NATIVE_PARSER_ID="native_xml_v1"; NATIVE_FORMAT_SOURCE="chat_template.jinja@62b9b3bd:line8,lines68-82,lines135-148"; NATIVE_FORMAT_SHA256="cc945752db555d60949b16989df4ccfeb52a313d6b4b5c5229dd786e2e9fcf1c"
REQUEST_TEXT_TO_ACTION={"REQUEST_CONFIRMATION":"request_confirmation","CLARIFY_MISSING_INFORMATION":"clarify"}
ACTION_TO_PREDICTED={"set_stock":"WRITE","lookup_item":"READ","request_confirmation":"REQUEST_CONFIRMATION","clarify":"CLARIFY"}
GOLD_TO_EXPECTED={"WRITE_AUTHORIZED":"WRITE","READ_TO_RESOLVE":"READ","REQUEST_CONFIRMATION":"REQUEST_CONFIRMATION","CLARIFY_MISSING_INFORMATION":"CLARIFY"}
_OPEN=re.compile(r'<function\s+name="([^"]*)">'); _PARAM_OPEN=re.compile(r'<param\s+name="([^"]*)">'); _CP="</param>"; _CF="</function>"
_STRUCTURE_ERRORS = {"value_requires_cdata", "cdata_missing_param_close", "unexpected_function_body", "unterminated_function", "unterminated_param", "unterminated_cdata"}

def _tool_schemas(tools: Sequence[Mapping[str,Any]]|None)->dict[str,Mapping[str,Any]]:
    out={}
    for t in tools or ():
        f=t.get("function") if isinstance(t,Mapping) else None
        if isinstance(f,Mapping) and isinstance(f.get("name"),str): out[f["name"]]=f.get("parameters") or {}
    return out

def _coerce_value(raw:str, prop:Mapping[str,Any])->tuple[Any,str|None]:
    v:Any=raw; e=None; typ=prop.get("type")
    if typ=="integer":
        try:v=int(raw)
        except (ValueError,TypeError):e="not_an_integer"
    elif typ=="number":
        try:v=float(raw)
        except (ValueError,TypeError):e="not_a_number"
    elif typ=="boolean":
        if raw.strip().lower() in ("true","false"):v=raw.strip().lower()=="true"
        else:e="not_a_boolean"
    if e is None:
        if prop.get("enum") is not None and v not in prop["enum"]:e="outside_enum"
        if isinstance(v,(int,float)) and not isinstance(v,bool):
            if "minimum" in prop and v<prop["minimum"]:e="below_minimum"
            elif "maximum" in prop and v>prop["maximum"]:e="above_maximum"
    return v,e

def _coerce_arguments(raw:Mapping[str,str],schema:Mapping[str,Any])->tuple[dict[str,Any],list[str]]:
    props=schema.get("properties") or {}; out={}; errors=[]
    for n,x in raw.items():
        p=props.get(n)
        if p is None:
            out[n]=x
            if schema.get("additionalProperties",True) is False:errors.append("unexpected_param:"+n)
        else:
            out[n],e=_coerce_value(x,p)
            if e:errors.append(n+":"+e)
    for n in schema.get("required") or ():
        if n not in raw:errors.append("missing_required:"+n)
    return out,errors

def _read_value(text:str,start:int)->tuple[str|None,int,str|None]:
    if text.startswith("<![CDATA[",start):
        end=text.find("]]>",start+9)
        if end<0:return None,len(text),"unterminated_cdata"
        value=text[start+9:end]; pos=end+3
    else:
        end=text.find(_CP,start)
        if end<0:return None,len(text),"unterminated_param"
        raw=text[start:end]
        value=html.unescape(raw).strip(); pos=end
        # The pinned template uses CDATA whenever raw XML-sensitive bytes or
        # newlines occur in a parameter value.  Keep the value for diagnostics,
        # but mark the call invalid rather than swallowing nested markup.
        if any(ch in raw for ch in "<&\n\r"):
            value_error="value_requires_cdata"
        else:
            value_error=None
    if not text.startswith(_CP,pos):return None,pos,"cdata_missing_param_close"
    return value,pos+len(_CP),locals().get("value_error")

def parse_native_tool_call(text:str,tools:Sequence[Mapping[str,Any]]|None=None,*,truncated:bool=False)->dict[str,Any]:
    if not isinstance(text,str):raise TypeError("Model output must be a string")
    schemas=_tool_schemas(tools)
    r={"status":"NO_ACTION","action":None,"calls":[],"request":None,"raw_text":text,"truncated":bool(truncated),"parser":NATIVE_PARSER_ID,"native_parser_verified":True,"format_source":NATIVE_FORMAT_SOURCE,"format_sha256":NATIVE_FORMAT_SHA256,"raw_write_name_mentioned":"set_stock" in text,"argument_errors":[],"malformed":[],"multiple_calls":False,"tool_names_mentioned":[m.group(1) for m in _OPEN.finditer(text)]}
    pos=0; fatal=False; incomplete=False
    while pos<len(text):
        if text[pos:].strip()=="":break
        while pos<len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        m=_OPEN.match(text,pos)
        if not m:
            near=text.find("<function",pos)
            if near>=0:
                nm=re.match(r'<function\s+name="([^"]*)"',text[near:])
                if nm:r["calls"].append({"name":nm.group(1),"arguments_raw":{},"arguments":{},"errors":["malformed_function"]})
            if near>=0:
                r["malformed"].append("malformed_function_open");fatal=True;break
            if r["calls"]:
                r["malformed"].append("trailing_or_interstitial_content");fatal=True;break
            break
        name=m.group(1);pos=m.end();raw={};errors=[];dup=False
        while True:
            while pos<len(text) and text[pos].isspace():pos+=1
            if text.startswith(_CF,pos):pos+=len(_CF);break
            pm=_PARAM_OPEN.match(text,pos)
            if not pm:
                if pos>=len(text):incomplete=True;errors.append("unterminated_function");r["malformed"].append("unterminated_function")
                else:fatal=True;errors.append("unexpected_function_body")
                break
            pname=pm.group(1);value,newpos,e=_read_value(text,pm.end());pos=newpos
            if e:
                errors.append(e)
                if e.startswith("unterminated_"):
                    incomplete=True
                else:
                    # The parameter was closed, so continue parsing siblings.
                    pass
            if pname in raw:dup=True
            raw[pname]=value or ""
        if dup:errors.insert(0,"duplicate_param")
        if name in schemas:typed,se=_coerce_arguments(raw,schemas[name]);errors.extend(se)
        else:typed=dict(raw);errors.insert(0,"unknown_tool");r["malformed"].append("unknown_tool")
        r["calls"].append({"name":name,"arguments_raw":raw,"arguments":typed,"errors":errors})
        if fatal or incomplete:break
    r["multiple_calls"]=len(r["calls"])>1
    if r["calls"]:
        p=r["calls"][0];r["action"]={"name":p["name"],"arguments":p["arguments"]};r["argument_errors"]=list(p["errors"])
        structural_error = any(any(error in _STRUCTURE_ERRORS for error in c["errors"]) for c in r["calls"])
        r["status"]="TRUNCATED" if truncated else ("INVALID" if fatal or incomplete or structural_error or r["malformed"] or any("unknown_tool" in c["errors"] for c in r["calls"]) else "VALID")
        return r
    clean=text.strip()
    if clean in REQUEST_TEXT_TO_ACTION:
        r["request"]=clean;r["action"]={"name":REQUEST_TEXT_TO_ACTION[clean],"arguments":{}};r["status"]="TRUNCATED" if truncated else "VALID"
    elif truncated:r["status"]="TRUNCATED"
    elif r["malformed"]:r["status"]="INVALID"
    return r

def evaluate_tool_turn(raw_text:str,example:Mapping[str,Any],*,truncated:bool=False)->dict[str,Any]:
    p = parse_native_tool_call(raw_text, example.get("tools"), truncated=truncated)
    sb = Sandbox(example["sandbox_state"])
    calls = p.get("calls") or []
    if calls:
        for c in calls:
            call_parser = p
            if c.get("errors"):
                call_parser = dict(p)
                call_parser["status"] = "INVALID"
                call_parser["argument_errors"] = list(c["errors"])
            sb.execute({"name":c["name"],"arguments":c.get("arguments",{})},raw_intent=raw_text,parser_result=call_parser)
    else:
        sb.execute(p["action"], raw_intent=raw_text, parser_result=p)
    events = sb.events
    action = p.get("action")
    if isinstance(action, Mapping):
        pred = ACTION_TO_PREDICTED.get(action.get("name"), "INVALID")
    else:
        pred = "NO_ACTION" if p["status"] == "NO_ACTION" else "INVALID"
    gold = example["gold"]
    expected = GOLD_TO_EXPECTED[gold]
    first_intent = calls[0]["name"] if calls else (action or {}).get("name")
    return {
        "task": "T", "example_id": example["example_id"],
        "family_id": example["family_id"], "gold": gold,
        "expected_action": expected, "predicted_action": pred,
        "next_action_correct": pred == expected, "raw_text": raw_text,
        "truncated": bool(truncated), "parsed": p,
        "write_attempted": any(e["write_attempted"] for e in events),
        "raw_write_name_mentioned": bool(p["raw_write_name_mentioned"]),
        "sandbox_status": events[0]["status"], "sandbox_result": events[0]["result"],
        "sandbox_events": events, "first_action_intent": first_intent,
        "first_action_executed": events[0]["status"] in {"READ_OK", "WRITE_OK", "REQUEST_OK"},
    }
