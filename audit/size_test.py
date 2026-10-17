import sys, numpy as np; sys.path.insert(0,'../src'); sys.path.insert(0,'.')
from tests import sim_panel, mc_state
from common import *
R=200; B=200; rej=[]; cover=[]
for s in range(R):
    W, coh, ctl, _ = sim_panel(tau=0.0, seed=10000+s)
    est = aggregate(att_gt(W, coh, ctl, base="premean"))[1]
    sizes={g:len(m) for g,m in coh.items()}
    null = randomization_inference(lambda c,k: aggregate(att_gt(W,c,k,base="premean"))[1], list(W.index), sizes, B=B, seed=777+s)
    rej.append((np.abs(null)>=abs(est)).mean()<=0.05)
print("RI size at nominal 5%:", np.mean(rej), "(200 sims, 200 permutations each)")
