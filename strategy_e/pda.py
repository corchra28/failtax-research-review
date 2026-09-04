"""Derivare PDA in Python pur (sha256 + verificare 'nu pe curba ed25519'). Verificata contra adreselor de tick arrays din pilot."""
import hashlib,struct
P=2**255-19; d=(-121665*pow(121666,P-2,P))%P
def _on_curve(b):
    y=int.from_bytes(b,"little")&((1<<255)-1)
    if y>=P: return False
    x2=(y*y-1)*pow(d*y*y+1,P-2,P)%P
    if x2==0: return True
    x=pow(x2,(P+3)//8,P)
    if (x*x-x2)%P!=0: x=x*pow(2,(P-1)//4,P)%P
    return (x*x-x2)%P==0
def b58d(s):
    A="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"; n=0
    for ch in s: n=n*58+A.index(ch)
    b=n.to_bytes(32,"big"); return b
def b58e(b):
    A="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"; n=int.from_bytes(b,"big"); s=""
    while n: n,r=divmod(n,58); s=A[r]+s
    return "1"*(len(b)-len(b.lstrip(b"\0")))+s
def find_pda(seeds,program):
    for bump in range(255,-1,-1):
        h=hashlib.sha256(b"".join(seeds)+bytes([bump])+program+b"ProgramDerivedAddress").digest()
        if not _on_curve(h): return b58e(h),bump
    raise ValueError
RAY=b58d("CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK")
def tick_array_address(pool,start_index): return find_pda([b"tick_array",b58d(pool),struct.pack(">i",start_index)],RAY)[0]
def array_start(tick,spacing): n=spacing*60; return (tick//n)*n
if __name__=="__main__":
    import json,base64
    man=json.load(open("pilot/manifest.json")); ok=bad=0
    for a,m in man["targets"].items():
        if m["size"]!=10240: continue
        raw=base64.b64decode(json.loads(open(f"pilot/state/{a}.jsonl").readline())["data"]); start=struct.unpack_from("<i",raw,40)[0]
        ok+= tick_array_address(m["pool"],start)==a; bad+= tick_array_address(m["pool"],start)!=a
    print(f"PDA tick arrays: {ok} corecte, {bad} gresite din {ok+bad}")
