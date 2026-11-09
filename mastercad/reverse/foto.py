"""Reverse engineering da foto: dal contorno fotografato a un disegno 2D in millimetri.

Due viste:
  - «alto": il pezzo fotografato dall'alto (piastre, flange, staffe, sagome) → contorno esterno + fori → ESTRUDI
  - «lato": un pezzo tornito fotografato di lato (perni, alberi, boccole) → mezza sezione sopra l'asse → RIVOLUZIONE
Scala, in due modi:
  - «a4": il pezzo è appoggiato su un foglio A4 bianco tutto inquadrato: il foglio dà scala e corregge la prospettiva;
  - «misura": l'utente dà una misura vera del pezzo (larghezza o altezza totale in mm).
Una foto non dice lo spessore né le parti nascoste: il risultato è una bozza da controllare e correggere nel Disegno.
"""
import base64
import math

import cv2
import numpy as np

A4 = (297.0, 210.0)       # mm
PX_MM_A4 = 4.0            # risoluzione del foglio raddrizzato
MAX_LATO = 1600


def _immagine(dati):
    if not dati:
        raise ValueError("Carica una foto del pezzo")
    arr = np.frombuffer(dati, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Formato non leggibile: usa JPG, PNG o WEBP")
    h, w = img.shape[:2]
    k = MAX_LATO / max(h, w)
    if k < 1:
        img = cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    return img


def _ordina_angoli(pts):
    pts = pts.reshape(4, 2).astype(np.float32)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def raddrizza_a4(img):
    """Trova il foglio A4 (il quadrilatero chiaro più grande) e lo raddrizza: 4 px = 1 mm."""
    grigio = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, chiaro = cv2.threshold(grigio, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    chiaro = cv2.morphologyEx(chiaro, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cont, _ = cv2.findContours(chiaro, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    foglio = None
    for c in sorted(cont, key=cv2.contourArea, reverse=True)[:5]:
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.15 * img.shape[0] * img.shape[1]:
            foglio = approx
            break
    if foglio is None:
        raise ValueError("Non trovo il foglio A4: inquadralo tutto, su un piano più scuro del foglio, senza riflessi")
    p = _ordina_angoli(foglio)
    lato1, lato2 = np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[3] - p[0])
    larg, alt = (A4[0], A4[1]) if lato1 >= lato2 else (A4[1], A4[0])
    W, H = int(larg * PX_MM_A4), int(alt * PX_MM_A4)
    M = cv2.getPerspectiveTransform(p, np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=np.float32))
    return cv2.warpPerspective(img, M, (W, H)), 1.0 / PX_MM_A4


def maschera_pezzo(img, bordo=0):
    """Il pezzo in bianco su nero. Sceglie da sola se il pezzo è più scuro o più chiaro dello sfondo."""
    grigio = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    h, w = grigio.shape
    if bordo:
        grigio = grigio[bordo:h - bordo, bordo:w - bordo]
        grigio = cv2.copyMakeBorder(grigio, bordo, bordo, bordo, bordo, cv2.BORDER_REPLICATE)
    migliore = None
    for modo in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        _, m = cv2.threshold(grigio, 0, 255, modo + cv2.THRESH_OTSU)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        cont, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in sorted(cont, key=cv2.contourArea, reverse=True)[:3]:
            x, y, cw, ch = cv2.boundingRect(c)
            tocca = x <= 2 or y <= 2 or x + cw >= w - 2 or y + ch >= h - 2
            a = cv2.contourArea(c)
            if tocca or a < 0.002 * w * h:
                continue
            if migliore is None or a > migliore[0]:
                pulita = np.zeros_like(m)
                cv2.drawContours(pulita, [c], -1, 255, -1)
                # fori: le zone di sfondo dentro il pezzo
                pulita = cv2.bitwise_and(pulita, m)
                migliore = (a, pulita)
            break
    if migliore is None:
        raise ValueError("Non distinguo il pezzo dallo sfondo: usa uno sfondo uniforme che contrasti (es. pezzo scuro su foglio bianco) e inquadra tutto il pezzo")
    return migliore[1]


def _cerchio_se_tondo(c):
    (x, y), r = cv2.minEnclosingCircle(c)
    if r < 2:
        return None
    pts = c.reshape(-1, 2).astype(float)
    dist = np.hypot(pts[:, 0] - x, pts[:, 1] - y)
    area = cv2.contourArea(c)
    if np.std(dist) / r < 0.04 and area / (math.pi * r * r) > 0.86:
        return (float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1]))), float(np.mean(dist))
    return None


def _semplifica(c, frazione=0.004):
    approx = cv2.approxPolyDP(c, max(1.0, frazione * cv2.arcLength(c, True)), True)
    return approx.reshape(-1, 2).astype(float)


def contorni_da_alto(maschera, mm_px):
    """Contorno esterno e fori → entità in mm (y verso l'alto; origine nell'angolo in basso a sinistra, al centro se il pezzo è tondo)."""
    cont, gerarchia = cv2.findContours(maschera, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not cont:
        raise ValueError("Nessun contorno trovato")
    i_est = max(range(len(cont)), key=lambda i: cv2.contourArea(cont[i]) if gerarchia[0][i][3] < 0 else -1)
    est = cont[i_est]
    x0, y0, cw, ch = cv2.boundingRect(est)
    tondo = _cerchio_se_tondo(est)
    # origine come la quota il tecnico: angolo in basso a sinistra, o il centro se il pezzo è tondo (flange, dischi)
    ox, oy = (tondo[0][0], tondo[0][1]) if tondo else (x0, y0 + ch)
    trasf = lambda p: [round((p[0] - ox) * mm_px, 2), round((oy - p[1]) * mm_px, 2)]
    entita, fori = [], 0
    if tondo:
        entita.append({"t": "circle", "c": trasf(tondo[0]), "r": round(tondo[1] * mm_px, 2)})
    else:
        entita.append({"t": "pline", "pts": [trasf(p) for p in _semplifica(est)], "closed": True})
    figlio = gerarchia[0][i_est][2]
    while figlio >= 0:
        c = cont[figlio]
        if cv2.contourArea(c) > 12:            # trascura i puntini
            t = _cerchio_se_tondo(c)
            if t:
                entita.append({"t": "circle", "c": trasf(t[0]), "r": round(t[1] * mm_px, 2)})
            else:
                entita.append({"t": "pline", "pts": [trasf(p) for p in _semplifica(c, 0.01)], "closed": True})
            fori += 1
        figlio = gerarchia[0][figlio][0]
    return entita, {"larghezza_mm": round(float(cw) * mm_px, 1), "altezza_mm": round(float(ch) * mm_px, 1), "fori": int(fori)}, (x0, y0, cw, ch)


def profilo_da_lato(maschera, mm_px):
    """Silhouette di un pezzo tornito → mezza sezione sopra l'asse (asse = linea orizzontale y=0)."""
    ys, xs = np.nonzero(maschera)
    if xs.size == 0:
        raise ValueError("Nessun pezzo trovato")
    x0, x1 = xs.min(), xs.max()
    raggi = []
    for x in range(x0, x1 + 1):
        col = np.nonzero(maschera[:, x])[0]
        raggi.append((col.max() - col.min()) / 2 if col.size else 0)
    raggi = np.array(raggi, dtype=float)
    # gradini: mediana a finestra stretta per togliere il rumore del bordo
    k = 5
    lisci = np.array([np.median(raggi[max(0, i - k):i + k + 1]) for i in range(len(raggi))])
    punti = [(0.0, 0.0)] + [(i * mm_px, r * mm_px) for i, r in enumerate(lisci)] + [((len(lisci) - 1) * mm_px, 0.0)]
    poly = np.array(punti, dtype=np.float32).reshape(-1, 1, 2)
    semplice = cv2.approxPolyDP(poly, max(0.15, 0.003 * (x1 - x0) * mm_px), True).reshape(-1, 2)
    pts = [[round(float(p[0]), 2), round(max(0.0, float(p[1])), 2)] for p in semplice]
    entita = [{"t": "pline", "pts": pts, "closed": True}]
    return entita, {"lunghezza_mm": round(float(x1 - x0) * mm_px, 1), "diametro_max_mm": round(float(2 * lisci.max()) * mm_px, 1)}, (x0, 0, x1 - x0, maschera.shape[0])


def anteprima(img, maschera):
    vista = img.copy()
    cont, _ = cv2.findContours(maschera, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vista, cont, -1, (40, 220, 255), max(2, img.shape[1] // 400))
    ok, png = cv2.imencode(".jpg", vista, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(png.tobytes()).decode()


def ricostruisci(dati, vista="alto", riferimento="misura", misura_mm=None, misura_di="larghezza"):
    if vista not in ("alto", "lato"):
        raise ValueError("Vista: «alto» (pezzo piatto) oppure «lato» (pezzo tornito)")
    img = _immagine(dati)
    avvisi = []
    if riferimento == "a4":
        img, mm_px = raddrizza_a4(img)
        maschera = maschera_pezzo(img, bordo=int(4 * PX_MM_A4))
        avvisi.append("Scala e prospettiva dal foglio A4 (precisione tipica ±0,5–1 mm con foto nitida e perpendicolare).")
    elif riferimento == "misura":
        try:
            misura_mm = float(misura_mm)
        except (TypeError, ValueError):
            raise ValueError("Scrivi una misura vera del pezzo in mm (es. larghezza totale 120)") from None
        if not 0.5 <= misura_mm <= 5000:
            raise ValueError("Misura di riferimento fuori campo (0,5–5000 mm)")
        maschera = maschera_pezzo(img)
        ys, xs = np.nonzero(maschera)
        px = (xs.max() - xs.min()) if misura_di == "larghezza" else (ys.max() - ys.min())
        if px < 10:
            raise ValueError("Pezzo troppo piccolo nella foto: avvicinati")
        mm_px = misura_mm / float(px)
        avvisi.append("Scala dalla misura data (%s = %g mm). Senza foglio A4 la prospettiva non è corretta: fotografa perpendicolare al pezzo." % (misura_di, misura_mm))
    else:
        raise ValueError("Riferimento: «a4» oppure «misura»")
    if vista == "alto":
        entita, info, _ = contorni_da_alto(maschera, mm_px)
        avvisi.append("La foto non mostra lo spessore: lo scegli tu con ESTRUDI.")
        comando = "ESTRUDI"
    else:
        entita, info, _ = profilo_da_lato(maschera, mm_px)
        avvisi.append("Profilo di rivoluzione: fori assiali, gole interne e filetti non si vedono di lato, vanno aggiunti a mano.")
        comando = "RIVOLUZIONE"
    avvisi.append("Ombre e riflessi spostano il contorno: controlla le quote con DIST prima di produrre.")
    return {"entita": entita, "info": info, "mm_per_pixel": round(mm_px, 5), "vista": vista,
            "comando_3d": comando, "avvisi": avvisi, "anteprima": anteprima(img, maschera)}
