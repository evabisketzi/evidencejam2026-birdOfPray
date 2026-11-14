import sys,os,collections,yaml; sys.path.insert(0,"dev")
from eval_murphy import *
p=graph_from_cache(os.environ.get("P","system.txt"),(SLUG,"4CB9X9XE","3KPITIV3","6HKWT4QG"))
E=yaml.safe_load(open(p))["edges"]
golds={"YKQQZV93":"dev/gold/murphy2005.yaml","4CB9X9XE":"dev/gold/4CB9X9XE.camo.yaml","3KPITIV3":"dev/gold/3KPITIV3.yaml","6HKWT4QG":"dev/gold/6HKWT4QG.yaml"}
K=["direct_causal","uncertain_causal","associational","no_relationship"]
def gedges(f):
    d=yaml.safe_load(open(f)); return [e for g in d["graphs"] for e in g["graph"]["edges"]] if "graphs" in d else d["edges"]
tv_all=[];out=[]
for s,f in golds.items():
    G=gedges(f); P=[e for e in E if e["source_document"]==s]
    gd=collections.Counter(e["causal_language"] for e in G); pd=collections.Counter(e["causal_language"] for e in P)
    tv=0.5*sum(abs(gd[k]/len(G)-pd[k]/len(P)) for k in K); tv_all.append(tv)
    out.append(f"{s}: TV {tv:.2f}  gold D/U/A/N {'/'.join(f'{gd[k]/len(G):.0%}' for k in K)}  ours {'/'.join(f'{pd[k]/len(P):.0%}' for k in K)}")
print(os.environ.get("CAMO_CALIBRATE"), "mean distance from gold distribution %.2f"%(sum(tv_all)/4)); [print("   ",o) for o in out]
