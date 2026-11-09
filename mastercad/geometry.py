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
    if kind not in ("plate","block","cylinder","l_bracket","flange"):
        raise ValueError("Forma non disponibile: piastra, blocco, cilindro, flangia o staffa a L")
    s={"kind":kind}
    if kind=="flange":
        for key in ("diameter","thickness","center_hole_diameter","bolt_circle_diameter","bolt_hole_diameter"):
            s[key]=number(spec.get(key),key)
        count=spec.get("bolt_hole_count",4)
        if not isinstance(count,int) or isinstance(count,bool) or count not in (3,4,6,8):
            raise ValueError("La flangia supporta 3, 4, 6 o 8 fori di fissaggio")
        s["bolt_hole_count"]=count
        outside_radius=s["diameter"]/2
        hole_radius=s["bolt_hole_diameter"]/2
        bolt_radius=s["bolt_circle_diameter"]/2
        center_radius=s["center_hole_diameter"]/2
        if center_radius>=outside_radius-1 or bolt_radius+hole_radius>=outside_radius-1:
            raise ValueError("Fori troppo vicini al bordo esterno della flangia")
        if bolt_radius-hole_radius<=center_radius+1:
            raise ValueError("Fori di fissaggio sovrapposti al foro centrale")
        if 2*bolt_radius*math.sin(math.pi/count)<=s["bolt_hole_diameter"]+1:
            raise ValueError("Fori di fissaggio troppo vicini fra loro")
    elif kind=="cylinder":
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
    if kind in ("cylinder","l_bracket","flange") and holes:raise ValueError("Questa forma non supporta ancora fori")
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
    if kind=="flange":
        shape=cq.Workplane("XY").circle(s["diameter"]/2).extrude(s["thickness"])
        center=cq.Workplane("XY").circle(s["center_hole_diameter"]/2).extrude(s["thickness"])
        shape=shape.cut(center)
        for index in range(s["bolt_hole_count"]):
            angle=2*math.pi*index/s["bolt_hole_count"]
            x=s["bolt_circle_diameter"]/2*math.cos(angle)
            y=s["bolt_circle_diameter"]/2*math.sin(angle)
            tool=cq.Workplane("XY").center(x,y).circle(s["bolt_hole_diameter"]/2).extrude(s["thickness"])
            shape=shape.cut(tool)
    elif kind=="cylinder":
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
