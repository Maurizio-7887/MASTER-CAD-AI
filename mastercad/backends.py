"""Image-to-CAD backends.

The CPU/OCR path works on Railway. The optional GPU provider is a separate
trusted worker under the operator's control; model weights and CUDA are NEVER
silently downloaded or executed by the web service.
"""
import json
import os
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .geometry import validate


def capability():
    url = os.getenv("MASTER_CAD_GPU_WORKER_URL", "").strip()
    key = os.getenv("MASTER_CAD_GPU_WORKER_TOKEN", "").strip()
    configured = bool(url and key)
    return {
        "active_backend": "remote-gpu" if configured else "online-cpu",
        "online_cpu": {"available": True, "features": ["text-to-cad", "dimension-ocr", "step-stl"]},
        "gpu": {
            "configured": configured,
            "available": False if not configured else None,
            "status": "worker_configured_not_probed" if configured else "waiting_for_cuda_worker",
            "note": "Img2CAD richiede checkpoint, ambiente CUDA e un worker separato. Non e' attivo nel container Railway."
        },
        "image_to_cad": {
            "photo_geometry_automatic": configured,
            "photo_geometry_verified": False,
            "manual_confirmation_required": True
        }
    }


def _safe_worker_url():
    url = os.getenv("MASTER_CAD_GPU_WORKER_URL", "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError("Configura un indirizzo HTTPS valido per il worker GPU")
    if parts.path not in ("", "/") or parts.query:
        raise ValueError("Il worker GPU deve essere indicato con il solo indirizzo base HTTPS")
    # Guardrail against accidental access to local/cloud metadata endpoints.
    import ipaddress
    try:
        ip = ipaddress.ip_address(parts.hostname)
        if not ip.is_global:
            raise ValueError("Usa un hostname pubblico HTTPS del worker GPU")
    except ValueError as exc:
        if "hostname pubblico" in str(exc):
            raise
    if parts.hostname.lower() in ("localhost", "localhost.localdomain") or parts.hostname.lower().endswith((".local", ".internal")):
        raise ValueError("Hostname privato non permesso")
    if parts.port not in (None, 443):
        raise ValueError("Il worker GPU deve utilizzare HTTPS sulla porta 443")
    return "https://" + parts.netloc + "/infer"


def infer_with_gpu(image_bytes, *, filename="drawing.png", category="mechanical_part"):
    """Submit a drawing to a configured external worker, not Railway's CPU.

    This implementation is intentionally conservative: the trusted worker
    must return a fully dimensioned, fixed-shape proposal. Arbitrary scripts,
    CadQuery code, model-generated Python and CAD command chains are rejected.
    """
    token = os.getenv("MASTER_CAD_GPU_WORKER_TOKEN", "").strip()
    if not token:
        raise ValueError("Worker NVIDIA non configurato: resta disponibile la modalita' OCR online")
    if not isinstance(image_bytes, bytes) or len(image_bytes)>4_000_000:
        raise ValueError("Immagine troppo grande (max 4 MB)")
    if category not in ("mechanical_part","chair","table","storagefurniture"):
        raise ValueError("Categoria non supportata")

    import base64
    body=json.dumps({"image_b64":base64.b64encode(image_bytes).decode("ascii"),"category":category},
                    separators=(",",":")).encode("utf8")
    req=urllib.request.Request(_safe_worker_url(),data=body,method="POST",headers={
        "Content-Type":"application/json",
        "Authorization":"Bearer "+token,
        "User-Agent":"MASTER-CAD-AI-GPU-Bridge/0.1",
    })
    try:
        with urllib.request.urlopen(req,timeout=25,context=ssl.create_default_context()) as response:
            if response.status != 200:
                raise RuntimeError("Worker GPU non disponibile")
            raw=response.read(150_000)
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("Impossibile contattare il worker GPU: riprova con l'OCR online") from exc
    try:
        data=json.loads(raw)
        if not isinstance(data,dict):
            raise ValueError()
        proposal=validate(data["spec"])
        return {
            "spec":proposal,"source":"gpu-worker",
            "verified":False,"requires_manual_confirmation":True,
            "note":"Proposta AI non verificata: misurare e correggere tutte le quote prima del CAD."
        }
    except (ValueError,KeyError,TypeError) as exc:
        raise RuntimeError("Risposta non valida dal worker GPU: nessun modello accettato") from exc
