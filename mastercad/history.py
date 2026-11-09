"""Human-readable construction history for the currently implemented solids.

Not a neural reverse-engineered original feature tree: this describes only
operations actually performed by the MASTER CAD AI parametric generator.
"""
from .geometry import validate


def operations(spec):
    s=validate(spec)
    kind=s["kind"]
    if kind=="flange":
        steps=[
            {"id":1,"operation":"sketch_circle","label":"Schizzo profilo esterno","parameters_mm":{"diameter":s["diameter"]}},
            {"id":2,"operation":"extrude","label":"Estrusione flangia","parameters_mm":{"thickness":s["thickness"]}},
            {"id":3,"operation":"pocket_through","label":"Foro centrale passante","parameters_mm":{"diameter":s["center_hole_diameter"]}},
            {"id":4,"operation":"circular_pattern","label":"Fori di fissaggio su circonferenza","parameters_mm":{
                "bolt_circle_diameter":s["bolt_circle_diameter"],
                "hole_diameter":s["bolt_hole_diameter"],"count":s["bolt_hole_count"]}}
        ]
    elif kind=="cylinder":
        steps=[
            {"id":1,"operation":"sketch_circle","label":"Schizzo cerchio","parameters_mm":{"diameter":s["diameter"]}},
            {"id":2,"operation":"extrude","label":"Estrusione cilindro","parameters_mm":{"height":s["height"]}}
        ]
    else:
        steps=[
            {"id":1,"operation":"sketch_rectangle","label":"Schizzo rettangolo","parameters_mm":{"length":s["length"],"width":s["width"]}},
            {"id":2,"operation":"extrude","label":"Estrusione base","parameters_mm":{"depth":s["thickness"]}}
        ]
        if kind=="l_bracket":
            steps.extend([
                {"id":3,"operation":"sketch_rectangle","label":"Schizzo parete verticale","parameters_mm":{"length":s["length"],"width":s["thickness"]}},
                {"id":4,"operation":"extrude_union","label":"Estrusione e unione parete verticale","parameters_mm":{"height":s["height"]}},
            ])
        if s["corner_radius"]:
            steps.append({"id":len(steps)+1,"operation":"fillet_vertical","label":"Raccordo bordi verticali","parameters_mm":{"radius":s["corner_radius"]}})
        for hole in s["holes"]:
            steps.append({
                "id":len(steps)+1,"operation":"pocket_through",
                "label":"Foro passante","parameters_mm":{
                    "x":hole["x"],"y":hole["y"],"diameter":hole["diameter"],
                    "depth":s["thickness"]
                }
            })
    return {"editable_parameters":s,"steps":steps,"source":"mastercad-generated",
            "note":"Cronologia della geometria generata dal nostro CAD, non reverse engineering automatico della foto."}
