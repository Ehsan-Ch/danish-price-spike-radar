"""Fixed-horizon logistic model; all data-dependent transforms use training only."""
from datetime import timedelta
import math
import numpy as np

HORIZON = 48
FEATURE_NAMES = [f"price_lag_{n}h" for n in (72,73,74,96,120,168,240)] + [
    "past_24h_mean","past_24h_std","past_24h_max","past_24h_min","past_change",
    "hour_sin","hour_cos","weekday_sin","weekday_cos","weekend"]

def features(series, target):
    # Issue is target -48h; newest observation starts issue -24h.
    # This buffer avoids assuming publication of undelivered prices.
    try:
        # The rolling-week benchmark requires this entire contiguous history.
        if any(target-timedelta(hours=h) not in series for h in range(72,241)):
            return None
        lags = [series[target-timedelta(hours=h)] for h in (72,73,74,96,120,168,240)]
        window = [series[target-timedelta(hours=h)] for h in range(72,96)]
    except KeyError:
        return None
    hour, weekday = target.hour, target.weekday()
    return np.array(lags + [float(np.mean(window)),float(np.std(window)),max(window),min(window),
        lags[0]-lags[3], math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24),
        math.sin(2*math.pi*weekday/7),math.cos(2*math.pi*weekday/7),float(weekday>=5)])

def samples(series):
    rows = []
    for t, price in sorted(series.items()):
        x = features(series, t)
        if x is not None:
            rows.append((t, price, x))
    return rows

def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z,-35,35)))

class Logistic:
    def fit(self, x, y, penalty=0.01):
        x, y = np.asarray(x,float), np.asarray(y,float)
        if len(x) < 50 or len(np.unique(y)) < 2:
            raise ValueError("Need at least 50 samples and both classes")
        self.mean = x.mean(axis=0)
        self.scale = x.std(axis=0)
        self.scale[self.scale < 1e-9] = 1
        z = np.column_stack([np.ones(len(x)), (x-self.mean)/self.scale])
        self.weights = np.zeros(z.shape[1])
        self.weights[0] = np.log(y.mean()/(1-y.mean()))
        lipschitz = np.linalg.norm(z,2)**2/(4*len(y)) + penalty
        for _ in range(2000):
            regularizer = penalty*self.weights.copy()
            regularizer[0] = 0
            grad = z.T@(sigmoid(z@self.weights)-y)/len(y)+regularizer
            self.weights -= grad/lipschitz
            if np.max(np.abs(grad)) < 1e-7:
                break
        return self

    def predict(self, x):
        x = np.asarray(x,float)
        z = np.column_stack([np.ones(len(x)), (x-self.mean)/self.scale])
        return sigmoid(z@self.weights)

    def export(self):
        return {"mean":self.mean.tolist(),"scale":self.scale.tolist(),
            "weights":self.weights.tolist(),"features":FEATURE_NAMES}

def auc(y, p):
    y, p = np.asarray(y,int), np.asarray(p,float)
    positive, negative = int(y.sum()), int((1-y).sum())
    if not positive or not negative:
        return None
    order = np.argsort(p,kind="stable")
    ranks = np.empty(len(y),float)
    i = 0
    while i < len(y):
        j = i+1
        while j<len(y) and p[order[j]]==p[order[i]]:
            j+=1
        ranks[order[i:j]] = (i+1+j)/2
        i=j
    return float((ranks[y==1].sum()-positive*(positive+1)/2)/(positive*negative))

def metrics(y, p, trigger=0.2):
    y,p = np.asarray(y,int),np.asarray(p,float)
    signal = p>=trigger
    tp = int(np.sum(signal & (y==1)))
    bins = []
    # Integer bin assignments avoid floating point boundary overlaps.
    bin_ids = np.minimum((p*10).astype(int),9)
    for i in range(10):
        mask = bin_ids==i
        if mask.any():
            bins.append({"lower":i/10,"n":int(mask.sum()),
                         "mean_probability":float(p[mask].mean()),"spike_rate":float(y[mask].mean())})
    return {"n":len(y),"spikes":int(y.sum()),"spike_rate":float(y.mean()),
        "brier":float(np.mean((p-y)**2)),
        "log_loss":float(-np.mean(y*np.log(np.clip(p,1e-12,1))+(1-y)*np.log(np.clip(1-p,1e-12,1)))),
        "auc":auc(y,p),"alerts":int(signal.sum()),
        "precision":tp/int(signal.sum()) if signal.any() else None,
        "recall":tp/int(y.sum()) if y.sum() else None,"reliability":bins}

