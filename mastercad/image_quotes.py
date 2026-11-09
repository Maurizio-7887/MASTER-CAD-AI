"""Offline OCR of user-supplied mechanical drawing dimensions.

This does not infer unseen geometry or assert that extracted dimensions are
correct. The operator must confirm all values before constructing a CAD solid.
"""
import io
import math
import re
import subprocess
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 12_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

def scan_dimensions(raw):
    if not isinstance(raw,str):
        raise ValueError("Testo OCR non valido")
    text=raw.lower().replace("×","x").replace("ø","diametro ").replace("⌀","diametro ").replace("φ","diametro ")
    text=re.sub(r"(?<=\d),(?=\d)",".",text)
    candidates=[]
    def add(field,value,source):
        try:n=float(value)
        except (TypeError,ValueError):return
        if math.isfinite(n) and .1<=n<=1000 and not any(c["field"]==field and c["value_mm"]==n for c in candidates):
            candidates.append({"field":field,"value_mm":n,"source":source[:100],"verified":False})
    words={"length":("lunghezza","length","lungo","lunga"),
           "width":("larghezza","width","largo","larga"),
           "thickness":("spessore","thickness","spesso","spessa"),
           "height":("altezza","height"),
           "diameter":("diametro","diameter")}
    num=r"(\d{1,4}(?:\.\d{1,3})?)"
    for field,labels in words.items():
        for label in labels:
            for m in re.finditer(r"\b"+label+r"\b\s*(?:[:=]|di|da)?\s*"+num+r"\s*(?:mm)?",text):
                add(field,m.group(1),m.group(0))
    for m in re.finditer(r"\b"+num+r"\s*[x]\s*"+num+r"\s*[x]\s*"+num+r"\s*(?:mm)?\b",text):
        for field,v in zip(("length","width","thickness"),m.groups()):
            add(field,v,m.group(0))
    return candidates[:25]

def inspect_image(data):
    if not isinstance(data,bytes) or not data:
        raise ValueError("Carica un'immagine PNG o JPEG")
    if len(data)>4_000_000:
        raise ValueError("Immagine troppo grande: massimo 4 MB")
    try:
        picture=Image.open(io.BytesIO(data))
        if picture.format not in ("PNG","JPEG","WEBP"):
            raise ValueError("Formato non valido: usa PNG, JPG oppure WEBP")
        picture=ImageOps.exif_transpose(picture)
        picture.thumbnail((1800,1800))
        picture=picture.convert("RGB")
        buffer=io.BytesIO()
        picture.save(buffer,format="PNG")
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as e:
        raise ValueError("Immagine non valida o non leggibile") from e
    try:
        result=subprocess.run(
            ["tesseract","stdin","stdout","-l","ita+eng","--psm","11"],
            input=buffer.getvalue(),capture_output=True,timeout=18,check=False
        )
    except FileNotFoundError:
        raise RuntimeError("OCR non installato nel server") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("Lettura OCR troppo lenta; prova un'immagine più nitida") from None
    if result.returncode:
        raise RuntimeError("Lettura OCR non riuscita")
    text=result.stdout.decode("utf-8","replace")[:4000]
    return {"text":text,"dimensions":scan_dimensions(text),
            "warning":"L'OCR può confondere numeri, unità, diametri e simboli. Correggi le misure e identifica la forma prima del CAD. Una foto senza quote non determina le dimensioni reali.",
            "geometry_inferred":False,"requires_manual_confirmation":True}
