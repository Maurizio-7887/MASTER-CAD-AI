"""Constrained Italian-language CAD specification interpreter. Never runs LLM code."""
import re
from .geometry import validate

N=r"(\d+(?:[.,]\d+)?)"
def num(s):return float(s.replace(",","."))

def find_value(text,words):
    for word in words:
        match=re.search(r"\b"+re.escape(word)+r"\b\s*(?:di|da|a|:|=)?\s*"+N+r"\s*(?:mm|millimetri)?",text)
        if match:return num(match.group(1))
    return None

def interpret(text,previous=None):
    t=(text or "").lower().strip()
    if not t:raise ValueError("Descrivi il pezzo: tipo e misure in millimetri")
    updating=bool(previous) and any(k in t for k in ("modifica","cambia","aumenta","riduci","allunga","accorcia","spessore","spessa","lunghezza","lunga","larghezza","larga","diametro","foro","fori","arrotonda","altezza","alta","alto"))
    if updating:
        spec=dict(previous)
    else:
        if any(k in t for k in ("staffa a l","staffa ad l","squadretta","staffa angolare")):kind="l_bracket"
        elif "flangia" in t:kind="flange"
        elif any(k in t for k in ("cilindro","disco")):kind="cylinder"
        elif "blocco" in t or "parallelepipedo" in t:kind="block"
        elif any(k in t for k in ("piastra","placca","staffa","supporto","basetta")):kind="plate"
        else:raise ValueError("Indica la forma: piastra, blocco, cilindro oppure staffa a L")
        spec={"kind":kind,"holes":[]}
    if spec["kind"]=="flange":
        mapping={
            "diameter":["diametro esterno","diametro flangia"],
            "thickness":["spessore","spessa"],
            "center_hole_diameter":["foro centrale","diametro foro centrale"],
            "bolt_circle_diameter":["interasse fori","diametro circonferenza fori"],
            "bolt_hole_diameter":["diametro fori fissaggio","fori fissaggio","fori da"]
        }
        for key,words in mapping.items():
            v=find_value(t,words)
            if v is not None:spec[key]=v
        count_match=re.search(r"\b(3|4|6|8)\s+fori\b",t)
        if count_match:spec["bolt_hole_count"]=int(count_match.group(1))
        else:
            for word,val in (("tre",3),("quattro",4),("sei",6),("otto",8)):
                if re.search(r"\b"+word+r"\s+fori\b",t):spec["bolt_hole_count"]=val;break
        missing=[key for key in mapping if key not in spec]
        if missing:
            raise ValueError("Per la flangia mancano: "+", ".join(missing)+". Esempio: flangia diametro esterno 100 spessore 12 foro centrale 30 interasse fori 70 quattro fori fissaggio 8")
        return validate(spec)
    if spec["kind"]=="cylinder":
        mapping={"diameter":["diametro"],"height":["altezza","alta","alto"]}
    else:
        mapping={"length":["lunghezza","lunga","lungo"],"width":["larghezza","larga","largo"],"thickness":["spessore","spessa","spesso"]}
        if spec["kind"]=="l_bracket":mapping["height"]=["altezza","alta","alto"]
    for key,words in mapping.items():
        v=find_value(t,words)
        if v is not None:spec[key]=v
    dims=re.search(N+r"\s*[x×]\s*"+N+r"(?:\s*[x×]\s*"+N+r")?",t)
    if dims and not updating and spec["kind"] in ("plate","block"):
        vals=[num(v) for v in dims.groups() if v is not None]
        for k,v in zip(("length","width","thickness"),vals):spec.setdefault(k,v)
    radius=find_value(t,["raggio","raccordo","arrotondamento"])
    if radius is not None:spec["corner_radius"]=radius
    if "senza fori" in t or "togli i fori" in t:spec["holes"]=[]
    if "foro" in t or "fori" in t:
        count_match=re.search(r"\b(\d{1,2})\s+fori?\b",t)
        count=int(count_match.group(1)) if count_match else None
        if count is None:
            for word,val in (("quattro",4),("un",1),("uno",1)):
                if re.search(r"\b"+word+r"\s+fori?\b",t):
                    count=val;break
        diameter=find_value(t,["diametro fori","diametro foro","diametro"])
        if diameter is None:
            match=re.search(r"\bfori?\s+(?:da|di)\s*"+N,t)
            if match:diameter=num(match.group(1))
        if count and diameter:
            if spec["kind"] not in ("plate","block"):raise ValueError("Fori supportati su piastre e blocchi")
            if count==4 and all(k in spec for k in ("length","width")):
                edge=max(3,min(15,diameter*1.3))
                x=spec["length"]/2-edge;y=spec["width"]/2-edge
                spec["holes"]=[{"x":a,"y":b,"diameter":diameter} for a,b in ((-x,-y),(-x,y),(x,-y),(x,y))]
            elif count==1:
                spec["holes"]=[{"x":0,"y":0,"diameter":diameter}]
            else:raise ValueError("Disponibili uno o quattro fori; per altre disposizioni servono quote esplicite")
    missing=[name for name in mapping if name not in spec]
    if missing:
        raise ValueError("Mancano le quote: "+", ".join(missing)+". Esempio: piastra lunghezza 120 larghezza 60 spessore 5")
    return validate(spec)
