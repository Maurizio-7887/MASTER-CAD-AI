"""Optional GPU worker entrypoint; deploy on an NVIDIA CUDA computer later.

This service is deliberately independent of Railway. It refuses to claim
inference is available until a real operator-installed adapter is configured
and a CUDA GPU is visible. It never returns placeholder or fabricated CAD.
"""
import base64
import importlib
import os
import secrets
from flask import Flask, request, jsonify
from mastercad.geometry import validate

app=Flask(__name__)
app.config["MAX_CONTENT_LENGTH"]=6_000_000


def readiness():
    try:
        import torch
        cuda=bool(torch.cuda.is_available())
        gpu=torch.cuda.get_device_name(0) if cuda else None
    except ImportError:
        cuda=False
        gpu=None
    adapter=os.environ.get("MASTER_CAD_IMAGE_MODEL_ADAPTER","").strip()
    return {
        "cuda":cuda,"gpu":gpu,
        "adapter_configured":bool(adapter),
        "ready":cuda and bool(adapter),
        "note":"Requires a tested Img2CAD-compatible adapter and pretrained checkpoints; no model is shipped or downloaded automatically."
    }


@app.before_request
def protect():
    if request.path=="/health":return
    secret=os.environ.get("MASTER_CAD_GPU_WORKER_TOKEN","")
    supplied=request.headers.get("Authorization","")
    if not secret or not secrets.compare_digest(supplied,"Bearer "+secret):
        return jsonify(error="Unauthorized"),401


@app.get("/health")
def health():
    # For security do not reveal GPU hardware details publicly.
    return jsonify(service="master-cad-gpu-worker",ok=True)


@app.get("/capabilities")
def capabilities():
    return jsonify(readiness())


@app.post("/infer")
def infer():
    state=readiness()
    if not state["ready"]:
        return jsonify(error="CUDA o modello Image-to-CAD non configurati"),503
    data=request.get_json(silent=True)
    if not isinstance(data,dict):
        return jsonify(error="JSON richiesto"),400
    if data.get("category") not in ("chair","table","storagefurniture","mechanical_part"):
        return jsonify(error="Categoria non supportata"),400
    try:
        raw=base64.b64decode(data["image_b64"],validate=True)
        if len(raw)>4_000_000:
            return jsonify(error="Immagine troppo grande"),413
        # Operator controls the trusted, local adapter. Never accept a module
        # path or Python expression from HTTP, and never execute model scripts.
        module_name, function_name=os.environ["MASTER_CAD_IMAGE_MODEL_ADAPTER"].split(":",1)
        callback=getattr(importlib.import_module(module_name),function_name)
        proposal=callback(raw,category=data["category"])
        if not isinstance(proposal,dict):
            raise ValueError("Risposta del modello non strutturata")
        spec=validate(proposal.get("spec"))
        return jsonify(spec=spec,verified=False,requires_manual_confirmation=True)
    except (KeyError,TypeError,ValueError,ImportError,AttributeError) as exc:
        app.logger.warning("Inference adapter failed: %s",type(exc).__name__)
        return jsonify(error="Modello non compatibile oppure risposta da verificare"),422
    except Exception:
        app.logger.exception("GPU inference failed")
        return jsonify(error="Errore inferenza GPU"),503
