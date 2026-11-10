"""Progetto guidato da carichi e vincoli: ottimizzazione topologica 2D (SIMP) e dimensionamento dello spessore.

Il tecnico dice: «questa staffa è fissata con 2 viti M10, regge 12 kN su questo perno, pesa al massimo 350 g,
qui deve passare l'aria». Il programma:
  1. riempie la sagoma con una griglia di elementi finiti (stato piano di tensione, elementi quadrati a 4 nodi);
  2. toglie materiale dove non lavora (SIMP con filtro di densità e aggiornamento «optimality criteria»,
     Andreassen et al. 2011), fino alla massa voluta, lasciando pieni gli anelli attorno a viti e perni;
  3. trasforma il risultato in un contorno vero (fori esatti per viti e perni) e quindi in un progetto modificabile;
  4. ricalcola tensioni e coefficiente di sicurezza sul pezzo finale e porta lo spessore al valore commerciale
     che lo rispetta (in piano la tensione va come 1/spessore).
È un calcolo deterministico e ripetibile, non un'AI che inventa. È una verifica 2D lineare: per pezzi critici serve il FEM.
"""
import math

import cv2
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from .. import profili
from ..materiali import materiale as dati_materiale
from ..progetto.lavorazioni import PASSAGGIO

SNERVAMENTO = {"S235": 235, "C45": 370, "42CrMo4": 650, "AISI304": 210, "AL6082": 250, "OTTONE": 250, "GHISA": 160, "POM": 60}
MODULO_E = {"S235": 210000, "C45": 210000, "42CrMo4": 210000, "AISI304": 193000, "AL6082": 70000, "OTTONE": 100000, "GHISA": 110000, "POM": 2800}
SPESSORI = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80)
NU = 0.3


def _ke():
    k = np.array([1 / 2 - NU / 6, 1 / 8 + NU / 8, -1 / 4 - NU / 12, -1 / 8 + 3 * NU / 8, -1 / 4 + NU / 12, -1 / 8 - NU / 8, NU / 6, 1 / 8 - 3 * NU / 8])
    idx = [[0, 1, 2, 3, 4, 5, 6, 7], [1, 0, 7, 6, 5, 4, 3, 2], [2, 7, 0, 5, 6, 3, 4, 1], [3, 6, 5, 0, 7, 2, 1, 4],
           [4, 5, 6, 7, 0, 1, 2, 3], [5, 4, 3, 2, 1, 0, 7, 6], [6, 3, 4, 1, 2, 7, 0, 5], [7, 2, 1, 4, 3, 6, 5, 0]]
    return 1 / (1 - NU ** 2) * k[np.array(idx)]


KE = _ke()


class Griglia:
    """Griglia di nelx × nely elementi quadrati di lato h che copre il riquadro del dominio."""

    def __init__(self, x0, y0, larg, alt, n_max=90):
        self.h = max(larg, alt) / n_max
        self.nelx = max(4, int(math.ceil(larg / self.h)))
        self.nely = max(4, int(math.ceil(alt / self.h)))
        self.x0, self.y0 = x0, y0
        self.nel = self.nelx * self.nely
        self.ndof = 2 * (self.nelx + 1) * (self.nely + 1)
        elx, ely = np.meshgrid(np.arange(self.nelx), np.arange(self.nely), indexing="ij")
        elx, ely = elx.ravel(), ely.ravel()
        n1 = (self.nely + 1) * elx + ely
        n2 = (self.nely + 1) * (elx + 1) + ely
        self.edof = np.stack([2 * n1 + 2, 2 * n1 + 3, 2 * n2 + 2, 2 * n2 + 3, 2 * n2, 2 * n2 + 1, 2 * n1, 2 * n1 + 1], 1)
        self.iK = np.kron(self.edof, np.ones((8, 1))).ravel().astype(int)
        self.jK = np.kron(self.edof, np.ones((1, 8))).ravel().astype(int)
        # centri degli elementi (y verso l'alto) e posizione dei nodi
        self.cx = x0 + (elx + 0.5) * self.h
        self.cy = y0 + (self.nely - ely - 0.5) * self.h
        ni, nj = np.meshgrid(np.arange(self.nelx + 1), np.arange(self.nely + 1), indexing="ij")
        self.nx = (x0 + ni * self.h).ravel()
        self.ny = (y0 + (self.nely - nj) * self.h).ravel()
        self.elx, self.ely = elx, ely

    def filtro(self, rmin):
        r = int(math.ceil(rmin)) - 1
        righe, col, val = [], [], []
        for i in range(self.nelx):
            for j in range(self.nely):
                e = i * self.nely + j
                for k in range(max(i - r, 0), min(i + r + 1, self.nelx)):
                    for l in range(max(j - r, 0), min(j + r + 1, self.nely)):
                        f = rmin - math.hypot(i - k, j - l)
                        if f > 0:
                            righe.append(e)
                            col.append(k * self.nely + l)
                            val.append(f)
        H = coo_matrix((val, (righe, col)), shape=(self.nel, self.nel)).tocsc()
        return H, np.asarray(H.sum(1)).ravel()

    def risolvi(self, x, penal, F, liberi, E=1.0, t=1.0):
        sK = (KE.ravel()[None, :] * (E * t * (1e-9 + x ** penal * (1 - 1e-9)))[:, None]).ravel()
        K = coo_matrix((sK, (self.iK, self.jK)), shape=(self.ndof, self.ndof)).tocsc()
        K = K[liberi, :][:, liberi]
        u = np.zeros(self.ndof)
        u[liberi] = spsolve(K, F[liberi])
        return u

    def tensioni(self, u, E):
        """Tensione di von Mises al centro di ogni elemento (MPa, se E in MPa e forze in N)."""
        h = self.h
        dnx = np.array([-1, 1, 1, -1]) / (2 * h)
        dny = np.array([-1, -1, 1, 1]) / (2 * h)
        B = np.zeros((3, 8))
        B[0, 0::2], B[1, 1::2] = dnx, dny
        B[2, 0::2], B[2, 1::2] = dny, dnx
        D = E / (1 - NU ** 2) * np.array([[1, NU, 0], [NU, 1, 0], [0, 0, (1 - NU) / 2]])
        s = (D @ B @ u[self.edof].T).T
        return np.sqrt(s[:, 0] ** 2 - s[:, 0] * s[:, 1] + s[:, 1] ** 2 + 3 * s[:, 2] ** 2)


def _maschera_dominio(g, dominio_ent):
    """Elementi dentro la sagoma di partenza (contorno del pezzo attuale); senza sagoma tutto il riquadro."""
    if not dominio_ent:
        return np.ones(g.nel, bool)
    facce, _, _ = profili._facce(dominio_ent)
    scala = 8.0 / g.h
    img = np.zeros((int(g.nely * 8) + 2, int(g.nelx * 8) + 2), np.uint8)
    for f in facce:
        for k, w in enumerate([f.outerWire()] + f.innerWires()):
            n = max(16, int(w.Length() / (g.h / 3)))
            pts = np.array([[(p.x - g.x0) * scala, (g.y0 + g.nely * g.h - p.y) * scala] for p in w.positions([i / n for i in range(n)])], np.int32)
            cv2.fillPoly(img, [pts], 255 if k == 0 else 0)
    px = ((g.cx - g.x0) * scala).astype(int).clip(0, img.shape[1] - 1)
    py = ((g.y0 + g.nely * g.h - g.cy) * scala).astype(int).clip(0, img.shape[0] - 1)
    return img[py, px] > 0


def ottimizza(spec):
    """spec: dominio {larghezza, altezza} oppure entità del contorno, spessore, materiale, viti [{x,y,vite|d}],
    carichi [{x,y,fx,fy,d?}] in N, zone_vietate [[x0,y0,x1,y1]], massa_max_g o frazione, sicurezza (coefficiente voluto)."""
    m_cod = str(spec.get("materiale") or "S235").upper()
    mat = dati_materiale(m_cod)
    E, sy = MODULO_E[m_cod], SNERVAMENTO[m_cod]
    t = float(spec.get("spessore") or 10)
    if not 1 <= t <= 200:
        raise ValueError("Spessore fra 1 e 200 mm")
    ent = spec.get("dominio_entita")
    if ent:
        bx = profili.estensione_entita(ent)
        x0, y0, L, H = bx[0], bx[1], bx[2] - bx[0], bx[3] - bx[1]
    else:
        L, H = float(spec.get("larghezza") or 0), float(spec.get("altezza") or 0)
        x0, y0 = 0.0, 0.0
        if not (5 <= L <= 3000 and 5 <= H <= 3000):
            raise ValueError("Indica la sagoma di partenza (larghezza e altezza in mm) o disegnala nel CAD")
    g = Griglia(x0, y0, L, H, max(30, min(120, int(spec.get("risoluzione") or 80))))
    dentro = _maschera_dominio(g, ent)
    solido, vuoto = np.zeros(g.nel, bool), ~dentro
    fissi = np.zeros(g.ndof, bool)
    F = np.zeros(g.ndof)
    viti = spec.get("viti") or []
    carichi = spec.get("carichi") or []
    if not viti:
        raise ValueError("Servono i punti di fissaggio (viti): almeno una")
    if not carichi:
        raise ValueError("Serve almeno un carico (forza in N)")
    fori = []
    for v in viti:
        x, y = float(v["x"]), float(v["y"])
        vite = str(v.get("vite") or "").upper()
        d = PASSAGGIO.get(vite) or float(v.get("d") or 9)
        d_vite = float(vite[1:]) if vite.startswith("M") else d - 1
        dist_n = np.hypot(g.nx - x, g.ny - y)
        ring = dist_n <= d / 2 + 0.5 * g.h
        fissi[2 * np.where(ring)[0]] = True
        fissi[2 * np.where(ring)[0] + 1] = True
        de = np.hypot(g.cx - x, g.cy - y)
        vuoto |= de < d / 2
        solido |= (de >= d / 2) & (de < d / 2 + max(d_vite * 0.9, 2.5 * g.h))
        fori.append({"x": x, "y": y, "d": d, "vite": vite or None})
    forza_tot = 0.0
    for c in carichi:
        x, y = float(c["x"]), float(c["y"])
        fx, fy = float(c.get("fx") or 0), float(c.get("fy") or 0)
        forza_tot = max(forza_tot, math.hypot(fx, fy))
        d = float(c.get("d") or 0)
        dist_n = np.hypot(g.nx - x, g.ny - y)
        if d > 0:       # perno: la forza si scarica sul bordo del foro
            nodi = np.where(np.abs(dist_n - d / 2) <= 0.75 * g.h)[0]
            de = np.hypot(g.cx - x, g.cy - y)
            vuoto |= de < d / 2
            solido |= (de >= d / 2) & (de < d / 2 + max(d * 0.6, 2.5 * g.h))
            fori.append({"x": x, "y": y, "d": d, "vite": None, "perno": True})
        else:
            nodi = np.where(dist_n <= 1.6 * g.h)[0]
            solido |= np.hypot(g.cx - x, g.cy - y) < 3 * g.h
        if not len(nodi):
            raise ValueError("Il carico in (%g; %g) è fuori dalla sagoma" % (x, y))
        F[2 * nodi] += fx / len(nodi)
        F[2 * nodi + 1] += fy / len(nodi)
    for z in spec.get("zone_vietate") or []:
        a, b, c_, d_ = (float(q) for q in z)
        vuoto |= (g.cx >= min(a, c_)) & (g.cx <= max(a, c_)) & (g.cy >= min(b, d_)) & (g.cy <= max(b, d_))
    solido &= ~vuoto
    attivi = ~(solido | vuoto)
    area_cella = g.h ** 2
    if spec.get("massa_max_g"):
        vol_max = float(spec["massa_max_g"]) / mat["densita"] * 1000      # mm³
        frazione = vol_max / t / area_cella / max(1, dentro.sum())
    else:
        frazione = float(spec.get("frazione") or 0.4)
    frazione = min(0.9, max(0.12, frazione))
    liberi = np.where(~fissi)[0]
    Hf, Hs = g.filtro(1.6)
    target = frazione * dentro.sum()
    x = np.where(solido, 1.0, np.where(vuoto, 0.0, frazione))
    xP = x.copy()
    storia = []
    for it in range(int(spec.get("iterazioni") or 60)):
        penal = min(3.0, 1.0 + it * 0.1)        # continuazione: da 1 a 3, evita i minimi locali
        u = g.risolvi(xP, penal, F, liberi)
        ue = u[g.edof]
        ce = np.einsum("ij,jk,ik->i", ue, KE, ue)
        c = float(((1e-9 + xP ** penal * (1 - 1e-9)) * ce).sum())
        dc = -penal * xP ** (penal - 1) * ce
        dv = np.ones(g.nel)
        dc = np.asarray(Hf * (dc / Hs))
        dv = np.asarray(Hf * (dv / Hs))
        l1, l2, mv = 0.0, 1e9, 0.2
        xn = x
        while (l2 - l1) / (l1 + l2 + 1e-30) > 1e-4:
            lm = 0.5 * (l1 + l2)
            xn = np.maximum(0, np.maximum(x - mv, np.minimum(1, np.minimum(x + mv, x * np.sqrt(np.maximum(-dc, 0) / dv / lm)))))
            xn[solido], xn[vuoto] = 1.0, 0.0
            xf = np.asarray(Hf * xn) / Hs
            xf[solido], xf[vuoto] = 1.0, 0.0
            if xf.sum() > target:
                l1 = lm
            else:
                l2 = lm
        cambio = float(np.abs(xn - x).max())
        x = xn
        xP = np.asarray(Hf * x) / Hs
        xP[solido], xP[vuoto] = 1.0, 0.0
        storia.append(round(c, 4))
        if it > 30 and cambio < 0.01:
            break
    return _risultato(g, xP, solido, vuoto, fori, F, liberi, E, sy, t, mat, m_cod, spec, storia, forza_tot, dentro)


def _risultato(g, xP, solido, vuoto, fori, F, liberi, E, sy, t, mat, m_cod, spec, storia, forza, dentro):
    # immagine della densità (y verso l'alto → riga 0 in alto), ingrandita e lisciata, poi contorni
    img = np.zeros((g.nely, g.nelx))
    img[g.ely, g.elx] = xP
    k = 6
    grande = cv2.resize(img, (g.nelx * k, g.nely * k), interpolation=cv2.INTER_CUBIC)
    grande = cv2.GaussianBlur(grande, (0, 0), k * 0.6)
    binaria = (grande > 0.5).astype(np.uint8) * 255
    pxmm = k / g.h
    for f in fori:      # i fori veri li fa il CAD: qui si riempiono, poi diventano lavorazioni esatte
        cx, cy = int((f["x"] - g.x0) * pxmm), int((g.y0 + g.nely * g.h - f["y"]) * pxmm)
        cv2.circle(binaria, (cx, cy), int(f["d"] / 2 * pxmm) + 2, 255, -1)
    n, etich, stat, _ = cv2.connectedComponentsWithStats(binaria, 8)
    if n <= 1:
        raise ValueError("Con questa massa non resta materiale: aumenta la massa o riduci il carico")
    tieni = 1 + int(np.argmax(stat[1:, cv2.CC_STAT_AREA]))
    binaria = np.where(etich == tieni, 255, 0).astype(np.uint8)
    cont, gerarchia = cv2.findContours(binaria, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    entita = []
    area_min = (3 * g.h * pxmm) ** 2
    for i, c in enumerate(cont):
        if cv2.contourArea(c) < area_min:
            continue
        c = cv2.approxPolyDP(c, 0.35 * k, True).reshape(-1, 2)
        if len(c) < 3:
            continue
        pts = [[round(g.x0 + px / pxmm, 3), round(g.y0 + g.nely * g.h - py / pxmm, 3)] for px, py in c]
        entita.append({"t": "pline", "pts": pts, "closed": True})
    if not entita:
        raise ValueError("Ottimizzazione senza forma utile: cambia carichi o vincoli")
    # verifica finale sul pezzo «vero» (0/1) con il carico reale
    bin_el = np.zeros(g.nel)
    piccola = cv2.resize(binaria, (g.nelx, g.nely), interpolation=cv2.INTER_AREA) / 255.0
    bin_el = (piccola[g.ely, g.elx] > 0.5).astype(float)
    bin_el[solido] = 1
    bin_el[vuoto] = 0
    u = g.risolvi(bin_el, 3, F, liberi, E=E, t=t)
    vm = g.tensioni(u, E) * (bin_el > 0.5)
    # il picco nel singolo elemento vicino ai vincoli è numerico: si usa il 99,5° percentile del materiale che lavora
    sigma = float(np.percentile(vm[bin_el > 0.5], 99.5)) if (bin_el > 0.5).any() else 0.0
    sic_voluta = float(spec.get("sicurezza") or 2.0)
    sic = sy / sigma if sigma > 0 else 99.0
    t_cons = t
    if sic < sic_voluta:
        t_cons = next((s for s in SPESSORI if s >= t * sic_voluta / sic), math.ceil(t * sic_voluta / sic))
    elif spec.get("riduci_spessore", True):
        t_min = t * sic_voluta / sic
        t_cons = next((s for s in SPESSORI if s >= t_min), t)
    sic_finale = sic * t_cons / t
    area_mm2 = sum(abs(cv2.contourArea(np.array(e["pts"], np.float32))) for e in entita[:1]) - \
        sum(abs(cv2.contourArea(np.array(e["pts"], np.float32))) for e in entita[1:]) - sum(math.pi * f["d"] ** 2 / 4 for f in fori)
    massa = area_mm2 * t_cons * mat["densita"] / 1000
    nodi_pieni = np.unique(g.edof[bin_el > 0.5].ravel())
    spost = float(np.abs(u[nodi_pieni]).max()) * t / t_cons if len(nodi_pieni) else 0.0
    lav = []
    for f in fori:
        foro = {"tipo": "foro", "x": f["x"], "y": f["y"], "d": round(f["d"], 3), "origine": "generativo"}
        lav.append(foro)
    lav.append({"tipo": "raccordo", "r": round(min(3.0, max(0.5, g.h * 0.8)), 1), "spigoli": "verticali"})
    lav.append({"tipo": "smusso", "d": 0.5, "spigoli": "superiori"})
    mappa = cv2.applyColorMap((np.clip(vm.reshape(g.nelx, g.nely).T / max(sy / sic_voluta, 1e-9), 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    mappa[(bin_el.reshape(g.nelx, g.nely).T < 0.5)] = (245, 245, 245)
    ok, png = cv2.imencode(".png", cv2.resize(mappa, (g.nelx * 4, g.nely * 4), interpolation=cv2.INTER_NEAREST))
    import base64
    avvisi = []
    if spec.get("massa_max_g") and massa > float(spec["massa_max_g"]) * 1.02:
        avvisi.append("Per reggere %s N con sicurezza %s serve lo spessore %s mm: il pezzo pesa %s g, oltre i %s g richiesti. "
                      "Puoi alzare la massa, scegliere un materiale più resistente o accettare una sicurezza più bassa."
                      % (_fmt(forza), _fmt(sic_voluta), _fmt(t_cons), _fmt(round(massa)), _fmt(float(spec["massa_max_g"]))))
    return {
        "progetto": {"base": {"tipo": "estrudi", "entita": entita, "altezza": t_cons}, "lavorazioni": lav, "materiale": m_cod},
        "massa_g": round(massa, 1), "spessore": t_cons, "spessore_iniziale": t, "tensione_max": round(sigma * t / t_cons, 1),
        "snervamento": sy, "sicurezza": round(sic_finale, 2), "sicurezza_voluta": sic_voluta, "spostamento_max_mm": round(spost, 3),
        "forza_n": forza, "iterazioni": len(storia), "elementi": int(dentro.sum()), "lato_elemento": round(g.h, 2),
        "mappa_tensioni": "data:image/png;base64," + base64.b64encode(png.tobytes()).decode(),
        "densita": {"nx": g.nelx, "ny": g.nely, "valori": [round(float(v), 2) for v in img.ravel()]},
        "avvisi": avvisi + ["Calcolo 2D lineare in stato piano di tensione: carichi nel piano del pezzo. Per pezzi critici, a fatica o con carichi fuori piano serve un FEM 3D.",
                   "Coefficiente di sicurezza sullo snervamento (%d MPa), tensione di von Mises al 99,5° percentile (i picchi puntuali sui vincoli sono numerici)." % sy],
    }


def _fmt(v):
    v = float(v)
    return ("%.2f" % v).rstrip("0").rstrip(".").replace(".", ",") if v % 1 else "{:,.0f}".format(v).replace(",", ".")
