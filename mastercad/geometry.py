"""Safe parametric geometry in mm. No execution of model-generated code."""
import math
import cadquery as cq

def number(value,name,minimum=.1,maximum=1000):
    try: value=float(value)
    except (ValueError,TypeError):raise ValueError(name+": misura numerica obbligatoria") from None
    if not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(name+": misura fuori intervallo "+str(minimum)+"–"+str(maximum)+" mm")
    return value

def validate(spec):
    if not isinstance(spec,dict):raise ValueError("Descrizione geometrica non valida")
    kind=spec.get("kind")
    if kind not in ("plate","block","cylinder","l_bracket"):
        raise ValueError("Forma non disponibile: piastra, blocco, cilindro o staffa a L")
    s={"kind":kind}
    if kind=="cylinder":
        for key in ("diameter","height"):s[key]=number(spec.get(key),key)
    else:
        for key in ("length","width","thickness"):s[key]=number(spec.get(key),key)
        if kind=="l_bracket":s["height"]=number(spec.get("height"),"height")
    try:radius=float(spec.get("corner_radius",0) or 0)
    except (ValueError,TypeError):raise ValueError("Raggio non valido") from None
    if not math.isfinite(radius) or radius<0:raise ValueError("Raggio non valido")
    if kind in ("plate","block","l_bracket") and radius>=min(s["length"],s["width"],s["thickness"])/2:
        raise ValueError("Raggio troppo grande rispetto allo spessore")
    s["corner_radius"]=radius if kind in ("plate","block") else 0
    holes=spec.get("holes",[])
    if not isinstance(holes,list) or len(holes)>16:raise ValueError("Massimo 16 fori")
    if kind in ("cylinder","l_bracket") and holes:raise ValueError("Questa forma non supporta ancora fori")
    s["holes"]=[]
    for hole in holes:
        if not isinstance(hole,dict):raise ValueError("Foro non valido")
        d=number(hole.get("diameter"),"diametro foro")
        try:x=float(hole.get("x",0));y=float(hole.get("y",0))
        except (ValueError,TypeError):raise ValueError("Coordinate foro non valide") from None
        if not math.isfinite(x) or not math.isfinite(y):raise ValueError("Coordinate foro non valide")
        if abs(x)+d/2>=s["length"]/2 or abs(y)+d/2>=s["width"]/2:
            raise ValueError("Foro troppo vicino al bordo")
        s["holes"].append({"x":x,"y":y,"diameter":d})
    return s

def build(spec):
    s=validate(spec);kind=s["kind"]
    if kind=="cylinder":
        shape=cq.Workplane("XY").circle(s["diameter"]/2).extrude(s["height"])
    elif kind=="l_bracket":
        foot=cq.Workplane("XY").box(s["length"],s["width"],s["thickness"],centered=(True,True,False))
        upright=(cq.Workplane("XY").box(s["length"],s["thickness"],s["height"],centered=(True,True,False))
                 .translate((0,s["width"]/2-s["thickness"]/2,0)))
        shape=foot.union(upright)
    else:
        shape=cq.Workplane("XY").box(s["length"],s["width"],s["thickness"],centered=(True,True,False))
        if s["corner_radius"]:shape=shape.edges("|Z").fillet(s["corner_radius"])
        for h in s["holes"]:
            cutter=cq.Workplane("XY").center(h["x"],h["y"]).circle(h["diameter"]/2).extrude(s["thickness"])
            shape=shape.cut(cutter)
    solid=shape.val()
    if solid.Volume()<=0:raise ValueError("Geometria vuota")
    return shape,solid,s

def mesh_data(solid,max_triangles=5000):
    vertices,faces=solid.tessellate(.8,.35)
    skip=max(1,math.ceil(len(faces)/max_triangles))
    triangles=[[[round(vertices[j].x,3),round(vertices[j].y,3),round(vertices[j].z,3)] for j in face] for face in faces[::skip]]
    box=solid.BoundingBox()
    return {"triangles":triangles,
            "bounds":{"x":round(box.xlen,3),"y":round(box.ylen,3),"z":round(box.zlen,3)},
            "volume_mm3":round(solid.Volume(),3)}
