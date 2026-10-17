"""Replay a recorded walk through a Python copy of the app's navigation logic (RouteTracker + RouteNavigator).

Checks, without walking: turn announcements, vibration patterns, arrival, and how well the
hallway heading correction recovers from not facing exactly down the hallway at Start.

Usage:
  python3 replay_navigation.py ROUTE.json SCAN_DIR ALIGNMENT.json [START_FACING_DEG] [--no-correct] [--debug]
"""
import sys, json, math, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__file__)); import place_landmarks as P

def wrap(d):
    d = math.fmod(d, 360)
    if d > 180: d -= 360
    if d <= -180: d += 360
    return d
def ang(v): return math.degrees(math.atan2(v[1], v[0]))
def rot(v, deg):
    r = math.radians(deg); return np.array([v[0]*math.cos(r)-v[1]*math.sin(r), v[0]*math.sin(r)+v[1]*math.cos(r)])

class Tracker:
    def __init__(s, pts, minturn=25):
        s.p=[np.array(p) for p in pts]; s.cum=[0.0]
        for i in range(1,len(s.p)): s.cum.append(s.cum[-1]+np.linalg.norm(s.p[i]-s.p[i-1]))
        s.total=s.cum[-1]; s.seg=0; s.turns=[]
        for k in range(1,len(s.p)-1):
            d=wrap(ang(s.p[k+1]-s.p[k])-ang(s.p[k]-s.p[k-1]))
            if abs(d)>=minturn: s.turns.append(dict(v=k,along=s.cum[k],deg=d,nxt=s.cum[k+1]-s.cum[k]))
    def project(s,q):
        def cl(i):
            a,b=s.p[i],s.p[i+1]; ab=b-a; l2=max(ab@ab,1e-9); t=min(1,max(0,(q-a)@ab/l2)); return s.cum[i]+t*math.sqrt(l2), np.linalg.norm(q-(a+ab*t))
        lo,hi=max(0,s.seg-1),min(len(s.p)-2,s.seg+2); best=(s.seg,0,1e9)
        for i in range(lo,hi+1):
            al,d=cl(i)
            if d<best[2]: best=(i,al,d)
        if best[2]>4:
            for i in range(len(s.p)-1):
                al,d=cl(i)
                if d<best[2]: best=(i,al,d)
        s.seg=best[0]; return best[1],best[2]
    def point(s,al):
        al=min(max(0,al),s.total)
        for i in range(len(s.p)-1):
            if al<=s.cum[i+1]:
                L=s.cum[i+1]-s.cum[i]; t=(al-s.cum[i])/L if L>0 else 0; return s.p[i]+(s.p[i+1]-s.p[i])*t
        return s.p[-1]
    def next_turn(s,al):
        for t in s.turns:
            if t['along']>al-0.5: return t

args=[a for a in sys.argv[1:] if not a.startswith('--')]
route=json.load(open(args[0])); SCAN=args[1]; ALIGN=args[2]
facing=float(args[3]) if len(args)>3 else -90
odo=P.load_odometry(SCAN)
def arkit_pose(o):
    # Stray poses are OpenCV-frame; ARKit's camera transform = R_cv * diag(1,-1,-1)
    R=o['R']@np.diag([1,-1,-1]); t=o['t']
    pos=np.array([t[0],-t[2]]); back=R[:,2]; fwd=np.array([-back[0],back[2]])
    if np.linalg.norm(fwd)<0.5: side=R[:,0]; fwd=np.array([-side[0],side[2]])
    return pos, ang(fwd)
TRUE_ROT=None  # set below: the MGH scan faced -77 deg at the start
tr=Tracker([(p['x'],p['y']) for p in route['points']])
p0,h0=arkit_pose(odo[0]); rotation=facing-h0; TRUE_ROT=-77-h0; origin=np.array([route['points'][0]['x'],route['points'][0]['y']])
al=json.load(open(ALIGN)); truth={round(p['t'],2):(p['x'],p['y']) for p in al['path']}
soon,now=set(),set(); arrived=None; log=[]; devs=[]; rels=[]
hist=[]; corrections=[]
CORRECT='--no-correct' not in sys.argv
DEBUG='--debug' in sys.argv
frames=sorted(odo); t0=None
import csv
ts={int(r[1]):float(r[0]) for r in list(csv.reader(open(SCAN+'/odometry.csv')))[1:]}
for f in frames[::6]:   # ~10 Hz like the app
    t=ts[f]-ts[0]; pos,h=arkit_pose(odo[f])
    q=origin+rot(pos-p0,rotation); head=h+rotation
    along,off=tr.project(q); rem=max(0,tr.total-along)
    hist.append(pos); hist[:]=hist[-60:]
    if CORRECT:
        old=None
        for hp in reversed(hist[:-1]):
            if np.linalg.norm(pos-hp)>=3.0: old=hp; break
        if old is not None:
            i0=next(i for i in range(len(hist)) if hist[i] is old)
            chord=pos-old; n=np.linalg.norm(chord)
            straight=max(abs(chord[0]*(hp[1]-old[1])-chord[1]*(hp[0]-old[0]))/n for hp in hist[i0:])
            if straight<0.4:
                walk_plan=ang(chord)+rotation
                best=None
                for i in range(len(tr.p)-1):
                    a,b=tr.p[i],tr.p[i+1]; L=np.linalg.norm(b-a)
                    if L<4: continue
                    ab=b-a; tt=min(1,max(0,(q-a)@ab/(ab@ab))); d=np.linalg.norm(q-(a+ab*tt))
                    if d>7: continue
                    delta=wrap(ang(ab)-walk_plan)
                    if abs(delta)<40 and (best is None or abs(delta)<abs(best[0])): best=(delta,i,a+ab*tt)
                if best:
                    delta,i,closest=best
                    qfix=q+(closest-q)*0.2
                    origin=qfix; p0=pos; rotation=rotation+0.3*delta; q=qfix; head=h+rotation
                    corrections.append(round(delta,1))
                    along,off=tr.project(q); rem=max(0,tr.total-along)
    tgt=tr.point(along+(1 if off>3 else 2.5)); rel=wrap(head-ang(tgt-q))
    # same bearing, but using the direction of travel instead of where the camera pointed
    if len(hist)>=8 and np.linalg.norm(hist[-1]-hist[-8])>0.6:
        mv=ang(rot(hist[-1]-hist[-8],rotation)); relm=wrap(mv-ang(tgt-q))
    else: relm=float('nan')
    rels.append((t,rel,off,rem,relm))
    if rem<1.5 and arrived is None: arrived=t; log.append((round(t,1),'ARRIVE: '+route['steps'][-1]['say'])); break
    nt=tr.next_turn(along)
    if nt:
        d=nt['along']-along; sp=('turn slightly ' if abs(nt['deg'])<60 else 'turn ')+('left' if nt['deg']>0 else 'right')
        if d<=1.2 and nt['v'] not in now: now.add(nt['v']); soon.add(nt['v']); log.append((round(t,1),f"{sp} now (buzz {'2' if nt['deg']>0 else '3'}) — at plan {np.round(q,1)}"))
        elif d<=4 and nt['v'] not in soon: soon.add(nt['v']); log.append((round(t,1),f"in {round(d)} m, {sp}"))
for l in log: print(l)
r=np.array([x[1] for x in rels]); o=np.array([x[2] for x in rels])
print(f"start facing assumed {facing}°, scanner actually faced {round(wrap(h0+rotation if False else h0+ (facing-h0)))}° in plan by construction; arrived at t={arrived}s")
print('heading corrections applied:',len(corrections),'final rotation error vs truth:',round(wrap(rotation-TRUE_ROT),1),'deg')
rm=np.array([x[4] for x in rels]); rm=rm[~np.isnan(rm)]
print(f"bearing vs direction of travel: median {np.median(rm):+.0f}°, |median| {np.median(abs(rm)):.0f}° (should be near 0 if signs are right)")
print(f"|arrow bearing| median {np.median(abs(r)):.0f}°, 90th pct {np.percentile(abs(r),90):.0f}°;  off-route distance median {np.median(o):.2f} m, max {o.max():.2f} m")
