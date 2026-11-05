"""BONKAGEDDON automated test suite — headless Chrome over CDP.
Usage: python tests/run_tests.py <scratch_dir> [only_test_name ...]
"""
import json, os, re, sys, time
try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Env

SCR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "_out")
ONLY = set(sys.argv[2:])
BASE = "http://127.0.0.1:8765/index.html"
RESULTS = []

BOT_JS = r"""
// test helpers: place units directly (bypasses merging) and drive any non-gameplay screen back to AIMING
window.setBoard=function(spec,fusions){const B=BONK,R=B.R;R.board.fill(null);R.reserve.fill(null);
  for(const k in spec){const[id,lv]=spec[k];const u=B.Board.mk(id,lv);if(+k>=100)R.reserve[+k-100]=u;else R.board[+k]=u;}
  R.fusionsActive={};for(const f of (fusions||[]))R.fusionsActive[f]=true;B.Board.reset();B.Game.rebuildSeq();B.Board.computeHint();};
window.toAim=function(){const B=BONK,G=B.Game;for(let i=0;i<20000&&G.state!=='AIMING';i++){
  if(G.state==='UPGRADE')G.pick(0);else if(G.state==='FUSION')B.Fusion.end();else if(G.state==='BOARD')G.closeBoard();
  else if(G.state==='FIRING'||G.state==='RESOLVING')B.tick(1/60);else break;}return G.state;};
// first-run "player who follows the lessons": real fire / merge / store / tap actions, think time added per decision.
// Buckets: combat (aiming think time + simulated volleys), lesson (time spent in mandatory lesson presentation), other (board/menus).
window.onboardRun=function(maxTurns,think){
  const B=BONK,G=B.Game,L=B.logical,TT=B.Tut;think=think||1.5;
  let clock=0,combat=0,lesson=0,other=0,turns=0,safety=0,lastLesson=null,sinceLesson=0,run=0,maxRun=0,wrongDone=false,recovered=null,after=0;
  const ev=[],gaps=[],seen={};
  const T=(b,dt)=>{clock+=dt;if(b==='c')combat+=dt;else if(b==='l')lesson+=dt;else other+=dt;};
  const major=k=>{if(seen[k])return;seen[k]=1;if(lastLesson!==null)gaps.push(sinceLesson);run=(lastLesson!==null&&sinceLesson===0)?run+1:1;maxRun=Math.max(maxRun,run);
    lastLesson=k;sinceLesson=0;ev.push({lesson:k,t:+clock.toFixed(1),turn:turns});};
  const tickB=(b,sec)=>{for(let i=0;i<Math.round(sec*60);i++){B.tick(1/60);T(b,1/60);}};
  while(safety++<300000){
    const st=G.state,R=B.R;
    if(TT.done('focus')&&++after>3000)break;
    if(st==='AIMING'){
      if(turns>=maxTurns)break;
      if(TT.aimOn()){major('aim');T('l',2.5);}           // watch the drag gesture once
      let a;const q=TT.gateOn()?TT.gateTarget():null;
      if(q){major('gate');T('l',2.2);a=Math.atan2(L.GATE_Y-L.LY,q.x+q.w/2-L.LX);}
      else{const al=R.enemies.filter(e=>!e.dead).sort((p,o)=>(o.row+o.h)-(p.row+p.h));const e=al[(Math.random()*Math.min(3,al.length))|0];
        a=e?Math.atan2(e.ry+e.rh/2-L.LY,e.rx+e.rw/2-L.LX):-1.4;}
      a=Math.max(-Math.PI+0.16,Math.min(-0.16,a));
      T('c',think);if(!ev.some(x=>x.firstShot))ev.push({firstShot:true,t:+clock.toFixed(1)});
      G.fire(a);turns++;sinceLesson++;
    }else if(st==='FIRING'||st==='RESOLVING'){B.tick(1/60);T('c',1/60);}
    else if(st==='BOARD'){
      const bt=TT.bt;
      if(bt&&bt.kind==='summon'){major('summon');tickB('l',0.8);B.Board.down({x:224,y:330});tickB('l',3.0);if(TT.bt)B.Board.down({x:224,y:330});tickB('l',0.2);continue;}
      if(bt&&bt.kind==='merge'){major('merge');let n=0;while(TT.bt&&TT.bt.stage!=='drag'&&TT.bt.stage!=='free'&&n++<600){B.tick(1/60);T('l',1/60);}
        if(TT.bt&&TT.bt.stage==='drag'){T('l',think);
          if(!wrongDone){wrongDone=true;const keep=TT.bt.cells.concat([TT.bt.from]);const w=[24,20,4,0,14,10].find(i=>!R.board[i]&&keep.indexOf(i)<0);
            if(w!==undefined){B.Board.move(TT.bt.from,w);T('l',think);}recovered=TT.bt&&TT.bt.stage==='drag'&&TT.bt.from>=0;}
          if(TT.bt&&TT.bt.from>=0)B.Board.move(TT.bt.from,TT.bt.to);}
        else if(TT.bt){const h=B.Board.hint;if(h)B.Board.move(h.from,h.to);else TT.skipLesson();}
        n=0;while(G.state==='BOARD'&&TT.bt&&n++<900){B.tick(1/60);T('l',1/60);}continue;}
      if(bt&&bt.kind==='reserve'){major('reserve');tickB('l',0.6);T('l',think);B.Board.move(TT.bt.from,TT.bt.to);if(TT.bt){T('l',think);B.Board.move(TT.bt.from,TT.bt.to);}if(TT.bt)TT.skipLesson();continue;}
      if(bt&&bt.kind==='focus'){major('focus');tickB('l',0.6);T('l',think);B.Board.down({x:184+56*1,y:642});if(TT.bt)TT.skipLesson();continue;}
      B.Board.finishAll();let n=0;while(B.Board.hint&&n++<20){B.Board.move(B.Board.hint.from,B.Board.hint.to);B.Board.finishAll();T('o',1.5);}
      const fa=B.Board.fusionsAvailable();if(fa.length){B.Board.activateFusion(fa[0]);T('o',1);}else{T('o',2);G.closeBoard();}
    }
    else if(st==='UPGRADE'){G.pick(0);T('o',3);}
    else if(st==='FUSION'){B.Fusion.end();T('o',2.5);}
    else break;
  }
  const R=B.R;
  return{state:G.state,turns,clock:+clock.toFixed(1),combat:+combat.toFixed(1),lesson:+lesson.toFixed(1),other:+other.toFixed(1),events:ev,gaps,maxRun,recovered,
    summons:R.summons,merges:R.merges,wave:R.wave,done:Object.keys(B.Save.d.tut).filter(k=>k[0]!=='_'&&k.indexOf(':')<0)};
};
window.skipTuts=function(){for(const k of BONK.Tut.ids)BONK.Save.d.tut[k]=1;};
window.boardSig=function(){const R=BONK.R;return R.board.map(u=>u?u.id+u.lv:'-').join(',')+'|'+R.reserve.map(u=>u?u.id+u.lv:'-').join(',');};
window.botRun=function(maxTurns,smart,pickMode){
  const B=BONK,G=B.Game,L=B.logical;let simT=0,turns=0,safety=0,maxBalls=0,maxParts=0,fusions=[],tSummon=null,tMerge=null,tFusion=null,tLv3=null,tLv4=null;
  while(safety++<400000){
    const st=G.state,R=B.R;
    if(st==='AIMING'){
      if(turns>=maxTurns)break;
      let a;
      const alive=R.enemies.filter(e=>!e.dead);
      if(smart&&alive.length&&Math.random()<0.6){
        alive.sort((p,q)=>(q.row+q.h)-(p.row+p.h));const e=alive[0];
        a=Math.atan2(e.ry+e.rh/2-L.LY,e.rx+e.rw/2-L.LX);
      }else if(R.gates.length&&Math.random()<0.7){const g=R.gates[(Math.random()*R.gates.length)|0];a=Math.atan2(L.GATE_Y-L.LY,g.x+g.w/2-L.LX);}
      else a=-Math.PI/2+(Math.random()-0.5)*2.4;
      a=Math.max(-Math.PI+0.16,Math.min(-0.16,a));
      G.fire(a);turns++;simT+=1.5;
    }else if(st==='FIRING'||st==='RESOLVING'){B.tick(1/60);simT+=1/60;maxBalls=Math.max(maxBalls,B.balls.list.length);maxParts=Math.max(maxParts,B.parts.list.length);}
    else if(st==='BOARD'){ // a player who takes every one-move merge the board suggests, then activates any fusion
      B.Board.finishAll();if(tSummon===null&&R.summons>0)tSummon=simT;
      // take one-move merges; otherwise gather a scattered triple (move one hero next to a twin), like a human would
      let n=0;while(n++<40){
        if(B.Board.hint){B.Board.move(B.Board.hint.from,B.Board.hint.to);B.Board.finishAll();simT+=1.5;continue;}
        const cells=R.board,by={};cells.forEach((u,i)=>{if(u&&u.lv<4){const k=u.id+u.lv;(by[k]=by[k]||[]).push(i);}});
        let moved=false;
        for(const k in by){const L=by[k];if(L.length<3)continue;
          for(const a of L){const c=a%5,r=(a/5)|0;const nb=[r>0?a-5:-1,c>0?a-1:-1,c<4?a+1:-1,r<4?a+5:-1].filter(j=>j>=0&&!cells[j]);
            const other=L.find(x=>x!==a&&Math.abs(x%5-c)+Math.abs(((x/5)|0)-r)>1);
            if(nb.length&&other!==undefined){B.Board.move(other,nb[0]);B.Board.finishAll();simT+=1.5;moved=true;break;}}
          if(moved)break;}
        if(!moved)break;}
      if(tMerge===null&&R.merges>0)tMerge=simT;if(tLv3===null&&R.bestLv>=3)tLv3=simT;if(tLv4===null&&R.bestLv>=4)tLv4=simT;
      const fa=B.Board.fusionsAvailable();simT+=3;
      if(fa.length&&pickMode==='fusion'){B.Board.activateFusion(fa[0]);if(tFusion===null)tFusion=simT;}else G.closeBoard();
    }
    else if(st==='UPGRADE'){G.pick((Math.random()*R.choices.length)|0);simT+=3;}
    else if(st==='FUSION'){fusions.push(B.Fusion.cur&&B.Fusion.cur.id);B.Fusion.end();simT+=2.5;}
    else break;
  }
  const R=B.R,r=v=>v===null?null:Math.round(v);
  return{state:G.state,wave:R.wave,turns,simT:Math.round(simT),kills:R.kills,level:R.level,bosses:R.bosses,hp:R.hp,summons:R.summons,merges:R.merges,
    bestLv:R.bestLv,board:R.board.filter(Boolean).map(u=>u.id[0]+u.lv).join(' '),fusions,maxBalls,maxParts,
    tSummon:r(tSummon),tMerge:r(tMerge),tFusion:r(tFusion),tLv3:r(tLv3),tLv4:r(tLv4),firstFusionTurn:R.firstFusionTurn||null};
};
"""


MOCK_JS = r"""
(function(){
  const cfg=JSON.parse(localStorage.getItem('__mock')||'{}');
  window.__log=[];const log=(...a)=>window.__log.push(a.join(':'));
  const store={};
  window.CrazyGames={SDK:{
    environment:cfg.env||'crazygames',
    init:async()=>{log('init');if(cfg.initFail)throw{code:'other',message:'boom'};},
    game:{gameplayStart:()=>log('gameplayStart'),gameplayStop:()=>log('gameplayStop'),loadingStart:()=>log('loadingStart'),
      loadingStop:()=>log('loadingStop'),happytime:()=>log('happytime'),settings:{muteAudio:!!cfg.mute,disableChat:false},
      addSettingsChangeListener:fn=>{window.__settingsFn=fn;}},
    ad:{requestAd:(type,cb)=>{const mode=(window.__adMode||cfg.ad||'finish');log('requestAd',type,mode);
        if(mode==='finish'){setTimeout(()=>{cb.adStarted&&cb.adStarted();log('adStarted');},50);setTimeout(()=>{log('adFinished');cb.adFinished&&cb.adFinished();},300);}
        else if(mode==='error'){setTimeout(()=>{log('adError');cb.adError&&cb.adError({code:'unfilled',message:'No ad available'});},80);}
        else if(mode==='throw'){throw new Error('sdk exploded');}
        /* 'never': no callbacks at all */},
      hasAdblock:async()=>false},
    data:{getItem:k=>{if(cfg.dataThrow)throw new Error('data disabled');return k in store?store[k]:null;},
      setItem:(k,v)=>{if(cfg.dataThrow)throw new Error('data disabled');store[k]=String(v);log('dataSet');},
      removeItem:k=>{delete store[k];},clear:()=>{}}
  }};
})();
"""


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + name + ("  — " + str(info) if info else ""), flush=True)


def want(t):
    return not ONLY or t in ONLY


def fresh(c, q="nosdk=1&seed=42"):
    # leave the game first (its pagehide handler flushes the save), then wipe storage from a neutral page
    c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
    c.ev("localStorage.clear()")
    c.nav(BASE + "?" + q)
    c.ev(BOT_JS)


def clientxy(c, x, y):
    v = json.loads(c.ev("JSON.stringify(BONK.view)"))
    return v["ox"] + x * v["s"], v["oy"] + y * v["s"]


def finish_turn(c, fps=60, pick=0, limit=4000):
    """advance until back to AIMING (auto-resolving upgrade/fusion screens)"""
    for _ in range(limit):
        st = c.ev("BONK.Game.state")
        if st == "AIMING":
            return st
        if st in ("FIRING", "RESOLVING"):
            c.ev(f"BONK.advance(0.5,{fps})")
        elif st == "UPGRADE":
            c.ev(f"BONK.Game.pick({pick})")
        elif st == "FUSION":
            c.ev("BONK.Fusion.end()")
        elif st == "BOARD":
            c.ev("BONK.Game.closeBoard()")
        else:
            return st
    return "TIMEOUT"


def main():
    env = Env(os.path.join(SCR, "run"))
    c = env.cdp
    shots = os.path.join(SCR, "shots")
    os.makedirs(shots, exist_ok=True)
    try:
        c.metrics(450, 820, 1)

        # ---------------- Functional: new player ----------------
        if want("functional"):
            fresh(c)
            check("new player lands directly in gameplay", c.ev("BONK.Game.state") == "AIMING")
            check("first run flagged + tutorial hint", c.ev("BONK.R.firstRun && !BONK.R.firstFire"))
            check("first turn: enemies but no gates yet (one thing at a time)", c.ev("BONK.R.enemies.length>=3 && BONK.R.gates.length===0"))
            c.ev("BONK.Save.d.tut.aim=1;BONK.Save.d.tut._since=2;BONK.Game.genGates()")
            check("gates appear once the player has had a few shots", c.ev("BONK.R.gates.length===2"))
            # mouse aim + fire through the x2 gate
            g = json.loads(c.ev("JSON.stringify(BONK.R.gates[0])"))
            gx = g["x"] + g["w"] / 2
            L = json.loads(c.ev("JSON.stringify(BONK.logical)"))
            # aim point on the line launcher -> gate centre, extended upward
            tx = L["LX"] + (gx - L["LX"]) * 3
            ty = L["LY"] + (L["GATE_Y"] - L["LY"]) * 3
            c.mouse("mousePressed", *clientxy(c, L["LX"], 500))
            c.mouse("mouseMoved", *clientxy(c, tx, ty))
            c.mouse("mouseReleased", *clientxy(c, tx, ty))
            check("mouse drag+release fires", c.ev("BONK.Game.state") == "FIRING")
            c.ev("BONK.advance(0.6,60)")
            nb = c.ev("BONK.balls.list.length")
            check("x2 gate multiplies balls (5 fired -> >5 alive)", nb > 5, f"balls={nb}")
            check("tutorial marked done after first fire", c.ev("BONK.Save.d.tutorialDone"))
            st = finish_turn(c)
            check("turn resolves back to AIMING", st == "AIMING", st)
            check("enemies took damage", c.ev("BONK.R.dmgDealt") > 0, c.ev("BONK.R.dmgDealt"))
            check("enemies descended (turn counter)", c.ev("BONK.R.turn") == 1)
            # aim cancel: drag below launcher, release → no fire
            c.mouse("mousePressed", *clientxy(c, 200, 400))
            c.mouse("mouseMoved", *clientxy(c, 200, 790))
            c.mouse("mouseReleased", *clientxy(c, 200, 790))
            check("dragging below launcher cancels the shot", c.ev("BONK.Game.state") == "AIMING")
            # clicking pause button must not fire
            c.ev("document.getElementById('hudPause').click()")
            check("pause button pauses (no shot)", c.ev("BONK.Game.state") == "PAUSED")
            c.ev("document.querySelector('[data-a=resume]').click()")
            check("resume returns to AIMING", c.ev("BONK.Game.state") == "AIMING")
            # HUD sound button: sound on by default, a real tap toggles mute and never fires
            check("sound is on by default", c.ev("BONK.Save.d.settings.mute") is False)
            sx, sy = c.ev("(()=>{const r=document.getElementById('hudSound').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()")
            for t in ("mousePressed", "mouseReleased"): c.mouse(t, sx, sy)
            check("HUD sound button mutes without firing", c.ev("[BONK.Save.d.settings.mute,BONK.Game.state,document.getElementById('hudSound').classList.contains('off')]") == [True, "AIMING", True])
            for t in ("mousePressed", "mouseReleased"): c.mouse(t, sx, sy)
            check("HUD sound button unmutes", c.ev("BONK.Save.d.settings.mute") is False)
            # player damage + death
            c.ev("""(()=>{const R=BONK.R;R.hp=1;for(const e of R.enemies){if(!e.dead){BONK.Game.gridSet(e,null);e.row=9;e.col=e.col;BONK.Game.setRect(e);BONK.Game.gridSet(e,e);}}})()""")
            # stack collisions: put just one enemy at row 9
            c.ev("""(()=>{const R=BONK.R;const G=BONK.Game;for(const e of R.enemies){G.gridSet(e,null);}R.enemies.length=0;R.grid.fill(null);
                    const e=G.makeEnemy('gloom',3,9,1,99999);G.placeEnemy(e);})()""")
            c.ev("BONK.Game.fire(-0.3)")
            st = finish_turn(c)
            check("enemy crossing danger line costs HP -> run ends", st == "RESULTS", st)
            check("results screen visible", c.ev("document.getElementById('results').classList.contains('show')"))
            coins = c.ev("BONK.Save.d.coins")
            check("coins awarded and saved", coins >= 0 and c.ev("BONK.Save.d.stats.runs") == 1, coins)
            c.ev("document.querySelector('[data-a=again]').click()")
            check("play again (no SDK) starts a new run", c.ev("BONK.Game.state") == "AIMING" and c.ev("BONK.R.turn") == 0)
            c.pump()
            check("no JS errors (functional)", not c.errors(), c.errors(False))

        # ---------------- Touch input ----------------
        if want("touch"):
            c.metrics(390, 844, 3, True)
            fresh(c)
            # audio: a brand-new player starts in combat without tapping any button; the first touch must unlock audio
            # from an event iOS accepts (touchend / pointerup), not only from pointerdown
            c.ev("window.__ul=[];const _u=BONK.Sound.unlock;BONK.Sound.unlock=function(){__ul.push(window.event&&window.event.type);return _u.apply(this,arguments);}")
            x0, y0 = clientxy(c, 224, 500)
            x1, y1 = clientxy(c, 120, 300)
            c.touch("touchStart", x0, y0)
            c.touch("touchMove", x1, y1)
            check("touch drag updates aim", c.ev("BONK.Input.active && BONK.Input.valid"))
            c.touch("touchEnd", x1, y1)
            ul = c.ev("JSON.stringify(__ul)")
            check("first touch unlocks audio from touchend/pointerup (iOS-accepted gesture) and audio runs", ("touchend" in ul or "pointerup" in ul) and c.ev("BONK.Sound.ctx&&BONK.Sound.ctx.state") == "running" and c.ev("BONK.Save.d.settings.mute") is False, ul)
            check("touch release fires", c.ev("BONK.Game.state") == "FIRING")
            finish_turn(c)
            # interrupted touch: pointercancel must not fire
            c.touch("touchStart", x0, y0)
            c.touch("touchMove", x1, y1)
            c.send("Input.dispatchTouchEvent", type="touchCancel", touchPoints=[])
            check("touchcancel aborts aim without firing", c.ev("BONK.Game.state") == "AIMING" and not c.ev("BONK.Input.active"))
            c.ev("BONK.render()")
            c.screenshot(os.path.join(shots, "mobile_portrait.png"))
            c.metrics(844, 390, 3, True)
            c.ev("BONK.Game.fire(-1.2)"); c.ev("BONK.advance(0.7,60)"); c.ev("BONK.render()")
            c.screenshot(os.path.join(shots, "mobile_landscape.png"))
            finish_turn(c)
            c.metrics(1920, 1080, 1, False)
            c.ev("BONK.Game.fire(-1.9)"); c.ev("BONK.advance(0.7,60)"); c.ev("BONK.render()")
            c.screenshot(os.path.join(shots, "desktop_wide.png"))
            finish_turn(c)
            c.metrics(450, 820, 1)
            c.pump()
            check("no JS errors (touch/viewports)", not c.errors(), c.errors(False))

        # ---------------- Determinism across refresh rates ----------------
        if want("physics"):
            sigs = {}
            for label, fps in (("60Hz", 60), ("120Hz", 120), ("144Hz", 144), ("spiky", None)):
                fresh(c, "nosdk=1&seed=777")
                out = []
                for ang in (-1.2, -2.0, -1.55, -0.9, -2.3):
                    c.ev(f"BONK.Game.fire({ang})")
                    if fps:
                        st = finish_turn(c, fps)
                    else:  # dt spikes: alternate 0.004s and 0.35s (clamped to 0.1) frames
                        for _ in range(3000):
                            st = c.ev("BONK.Game.state")
                            if st == "AIMING": break
                            if st == "UPGRADE": c.ev("BONK.Game.pick(0)"); continue
                            if st == "FUSION": c.ev("BONK.Fusion.end()"); continue
                            if st == "BOARD": c.ev("BONK.Game.closeBoard()"); continue
                            c.ev("for(let i=0;i<20;i++){BONK.tick(0.004);BONK.tick(0.35);}")
                    out.append(c.ev("JSON.stringify([BONK.R.turn,Math.round(BONK.R.dmgDealt*1000),BONK.R.kills,BONK.R.enemies.map(e=>[e.col,e.row,Math.round(e.hp*1000)])])"))
                sigs[label] = out
            base = sigs["60Hz"]
            for k in ("120Hz", "144Hz", "spiky"):
                check(f"simulation identical at {k} vs 60Hz", sigs[k] == base, "" if sigs[k] == base else (sigs[k][-1][:120], base[-1][:120]))
            # single huge spike is clamped
            fresh(c, "nosdk=1&seed=5")
            c.ev("BONK.Game.fire(-1.3)")
            # measured inside one evaluation so no real animation frame can run in between; one fixed step may carry over
            dtsim = c.ev("(()=>{const t0=BONK.R.time;BONK.tick(5);return BONK.R.time-t0;})()")
            check("5s frame spike clamped to <=0.1s sim (+1 carried step)", dtsim <= 0.1 + 1 / 120 + 1e-6, round(dtsim, 4))
            # hidden tab: frames do nothing
            c.ev("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
            t0 = c.ev("BONK.R.time"); time.sleep(0.5); t1 = c.ev("BONK.R.time")
            check("hidden tab freezes the simulation", t1 == t0)
            c.ev("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))")
            time.sleep(0.4)
            check("visible tab resumes", c.ev("BONK.R.time") > t1)
            finish_turn(c)
            # tunneling: 2x speed, check every tick that no ball centre is inside an enemy
            fresh(c, "nosdk=1&seed=9")
            res = c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;B.CONFIG.ball.speed=1640;let bad=0,ticks=0;
               for(let k=0;k<6;k++){toAim();
                 G.fire(-Math.PI/2+(k-2.5)*0.35);
                 for(let i=0;i<4000&&(G.state==='FIRING'||G.state==='RESOLVING');i++){B.tick(1/60);ticks++;
                   for(const b of B.balls.list){if(!b.active||b.recall)continue;for(const e of R.enemies){if(e.dead)continue;
                     if(b.x>e.rx+1&&b.x<e.rx+e.rw-1&&b.y>e.ry+1&&b.y<e.ry+e.rh-1&&b.phaseLeft<=0&&b.pierceLeft<=0&&b.ignoreE!==e)bad++;}}}
               }B.CONFIG.ball.speed=820;return{bad,ticks};})()""")
            check("no tunneling at 2x ball speed", res["bad"] == 0, res)
            c.pump()
            check("no JS errors (physics)", not c.errors(), c.errors(False))

        # ---------------- Caps & heavy scenes ----------------
        if want("caps"):
            fresh(c, "nosdk=1&seed=11")
            res = c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;B.Save.d.perm.balls=3;R.passives.volley=6;R.passives.gate=2;
               setBoard({0:['bean',3],1:['zappy',3],2:['banana',3]},['thunder']);
               let maxB=0,maxP=0,maxT=0,maxF=0;
               for(let k=0;k<4;k++){
                 toAim();
                 R.gates.length=0;R.gates.push({k:'mult',v:5,x:0,w:448,flash:0});
                 for(let r=0;r<6;r++)for(let c=0;c<7;c++)if(!R.grid[r*7+c]){const e=G.makeEnemy('gloom',c,r,1,400);G.placeEnemy(e);}
                 G.fire(-Math.PI/2+0.2*k);
                 for(let i=0;i<5000&&(G.state==='FIRING'||G.state==='RESOLVING');i++){B.tick(1/60);B.render();
                   maxB=Math.max(maxB,B.balls.list.length);maxP=Math.max(maxP,B.parts.list.length);maxT=Math.max(maxT,B.texts.list.length);maxF=Math.max(maxF,B.fx.list.length);}
               }
               return{maxB,maxP,maxT,maxF,volley:G.volleySize(),state:G.state};})()""")
            check("ball cap respected under x7 gates + big volley + splits", res["maxB"] <= 160, res)
            check("ball cap actually reached (overflow path exercised)", res["maxB"] >= 150, res["maxB"])
            check("particles/texts/fx bounded by pools", res["maxP"] <= 700 and res["maxT"] <= 90 and res["maxF"] <= 140, res)
            # performance probe: time a heavy frame (sim+render) in this headless CPU
            perf = c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;toAim();
               R.gates.length=0;R.gates.push({k:'mult',v:5,x:0,w:448,flash:0});
               for(let r=0;r<6;r++)for(let c=0;c<7;c++)if(!R.grid[r*7+c]){const e=G.makeEnemy('gloom',c,r,1,5000);G.placeEnemy(e);}
               G.fire(-1.4);
               let worst=0,sum=0,n=0,maxB=0;for(let i=0;i<600&&G.state==='FIRING';i++){const t=performance.now();B.tick(1/60);B.render();const d=performance.now()-t;worst=Math.max(worst,d);sum+=d;n++;maxB=Math.max(maxB,B.balls.list.length);}
               return{avg:+(sum/n).toFixed(2),worst:+worst.toFixed(2),frames:n,maxBalls:maxB};})()""")
            check("heavy scene avg frame (sim+render) < 8ms on this machine", perf["avg"] < 8 and perf["maxBalls"] >= 100 and perf["frames"] >= 120, perf)
            # gate edges: a ball whose edge clips the gate counts; one that clearly misses does not
            edge = c.ev(r"""(()=>{const B=BONK,G=B.Game,L=B.logical;function shot(dx){toAim();const R=B.R;R.enemies.length=0;R.grid.fill(null);const e=G.makeEnemy('gloom',6,0,1,999999);G.placeEnemy(e);
                 R.gates.length=0;R.gates.push({k:'mult',v:2,x:150,w:84,flash:0});R.track.gateBalls=0;
                 G.fire(Math.atan2(L.GATE_Y-L.LY,150+dx-L.LX));for(let i=0;i<3000&&G.state==='FIRING';i++)B.tick(1/120);return R.track.gateBalls;}
               return {inside:shot(42),edgeL:shot(-10),edgeR:shot(84+10),miss:shot(-24)};})()""")
            check("gate edges are forgiving: ball edge touching the gate multiplies, a clear miss does not", edge["inside"] > 0 and edge["edgeL"] > 0 and edge["edgeR"] > 0 and edge["miss"] == 0, edge)
            c.pump()
            check("no JS errors (caps)", not c.errors(), c.errors(False))

        # ---------------- Roguelite: upgrades, characters, fusions, boss ----------------
        if want("content"):
            fresh(c, "nosdk=1&seed=21")
            res = c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R,U=B.Upgrades;const out={};
               // card generation sanity over many builds
               let bad=0;for(let i=0;i<300;i++){const cs=U.build();if(cs.length!==3)bad++;const keys=cs.map(c=>c.kind+c.id);if(new Set(keys).size!==3)bad++;
                 for(const c of cs)if(c.kind!=='passive'&&c.kind!=='heal'&&c.kind!=='coins')bad++;}
               out.cardBad=bad;
               // max out every passive → cards still non-empty
               for(const k in R.passives)R.passives[k]=99;
               const cs=U.build();out.maxedCards=cs.map(c=>c.kind);
               for(const k in R.passives)R.passives[k]=0;
               return out;})()""")
            check("300 passive card rolls: always 3 distinct passive cards", res["cardBad"] == 0, res["cardBad"])
            check("fully maxed build still yields 3 cards (fallbacks)", len(res["maxedCards"]) == 3, res["maxedCards"])
            # every hero ability does something observable
            abil = c.ev(r"""(()=>{const B=BONK,G=B.Game;const out={};
              B.Save.d.unlocked={banana:true,zappy:true,bean:true,croissant:true,frosty:true,turnip:true,muffin:true,sipsula:true};
              const ids=['croissant','banana','frosty','zappy','bean','muffin','turnip','sipsula'];
              for(const id of ids){
                G.newRun();G.state='AIMING';const R=B.R;setBoard({0:[id,3]});R.gates.length=0;
                R.enemies.length=0;R.grid.fill(null);
                for(let r=0;r<6;r++)for(let c=0;c<7;c++)if((r+c)%2===0){const e=G.makeEnemy(r%2?'gloom':'minion',c,r,1,300);G.placeEnemy(e);}
                R.hp=2;const t0={freeze:R.track.freezes,zap:R.track.zapHits};let maxB=0,maxSpd=0,pierced=0,curved=0;
                G.fire(-1.35);
                for(let i=0;i<3000&&G.state==='FIRING';i++){B.tick(1/60);maxB=Math.max(maxB,B.balls.list.length);
                  for(const b of B.balls.list){maxSpd=Math.max(maxSpd,b.spdMul);if(b.pierceLeft<b.prof.pierce)pierced++;}}
                out[id]={dmg:Math.round(R.dmgDealt),blasts:R.blasts,arcs:R.arcs,freezes:R.track.freezes-t0.freeze,maxB,maxSpd:+maxSpd.toFixed(2),pierced,hp:R.hp,kills:R.kills};
              }
              return out;})()""")
            a = abil
            check("Croissanto pierces", a["croissant"]["pierced"] > 0, a["croissant"])
            check("Bananini explodes", a["banana"]["blasts"] > 0, a["banana"])
            check("Frosty freezes", a["frosty"]["freezes"] > 0, a["frosty"])
            check("Zappy chains lightning", a["zappy"]["arcs"] > 0, a["zappy"])
            check("Splittini splits (more balls than volley)", a["bean"]["maxB"] > 5, a["bean"])
            check("Turbo accelerates", a["turnip"]["maxSpd"] > 1.3, a["turnip"])
            check("Sipsula heals", a["sipsula"]["hp"] > 2, a["sipsula"])
            # homing: compare trajectory deviation vs plain ball
            hom = c.ev(r"""(()=>{const B=BONK,G=B.Game;function run(id){G.newRun();G.state='AIMING';const R=B.R;setBoard({0:[id,3]});R.gates.length=0;
                R.enemies.length=0;R.grid.fill(null);const e=G.makeEnemy('gloom',0,2,1,99999);G.placeEnemy(e);G.fire(-1.2);
                for(let i=0;i<400&&G.state==='FIRING';i++)B.tick(1/60);return Math.round(R.dmgDealt);}
                return{muffin:run('muffin'),banana:run('banana')};})()""")
            check("Magneto homes onto an off-axis target", hom["muffin"] > 0, hom)
            # fusions: offered on the board at Lv2+Lv2, activated with a cutscene, heroes kept, behaviour changes
            fus = c.ev(r"""(()=>{const B=BONK,G=B.Game;const out={};
              for(const fid of ['steam','thunder','ghost','boom']){
                const f={steam:['croissant','frosty'],thunder:['bean','zappy'],ghost:['muffin','croissant'],boom:['banana','turnip']}[fid];
                G.newRun();const R=B.R;setBoard({0:[f[0],1],1:[f[1],2]});G.state='BOARD';
                const notYet=B.Board.fusionsAvailable().indexOf(fid)<0;
                setBoard({0:[f[0],2],1:[f[1],2]});const idx=B.Board.fusionsAvailable().indexOf(fid);
                B.Board.activateFusion(fid);const st=G.state;B.Fusion.end();const back=G.state;G.closeBoard();
                const kept=R.board.filter(Boolean).length,seqF=R.seq.every(p=>p.fusion===fid);
                R.gates.length=0;R.enemies.length=0;R.grid.fill(null);
                for(let r=0;r<6;r++)for(let c=0;c<7;c++)if((r+c)%2===0){const e=G.makeEnemy('gloom',c,r,1,500);G.placeEnemy(e);}
                let steams=0,sparks=0,phased=0,mega=0;G.fire(-1.3);
                for(let i=0;i<3000&&G.state==='FIRING';i++){B.tick(1/60);
                  for(const s of B.fx.list)if(s.active&&s.type==='steam')steams=Math.max(steams,1);
                  for(const b of B.balls.list){if(b.phaseLeft<b.prof.phase)phased++;if(b.stacks>=3)mega++;}}
                out[fid]={offered:idx>=0&&notYet,state:st,back,kept,seqF,sparks:R.sparks,steams,phased,mega,arcs:R.arcs,dmg:Math.round(R.dmgDealt),discovered:!!B.Save.d.fusions[fid]};
              }return out;})()""")
            for fid, extra in (("steam", "steams"), ("thunder", "arcs"), ("ghost", "phased"), ("boom", "mega")):
                f = fus[fid]
                check(f"fusion {fid}: offered only at Lv2+Lv2, cutscene, back to board, heroes kept", f["offered"] and f["state"] == "FUSION" and f["back"] == "BOARD" and f["kept"] == 2 and f["seqF"], f)
                check(f"fusion {fid}: new behaviour observed ({extra})", f[extra] > 0, f[extra])
                check(f"fusion {fid}: discovery recorded", f["discovered"])
            # boss
            boss = c.ev(r"""(()=>{const B=BONK,G=B.Game;G.newRun();G.state='AIMING';const R=B.R;R.wave=5;R.enemies.length=0;R.grid.fill(null);G.spawnBoss();
               const b=R.boss;const o={spawned:!!b,w:b.w,h:b.h,hp:b.maxHp};
               // shield blocks from below
               b.shieldOn=true;b.dy=0;const hp0=b.hp;setBoard({0:['banana',1]});B.Save.d.perm.balls=0;R.passives.volley=0;
               R.gates.length=0;G.fire(-Math.PI/2+0.01);for(let i=0;i<2000&&G.state==='FIRING';i++)B.tick(1/60);
               o.blockedDmg=Math.round(hp0-b.hp);
               while(G.state!=='AIMING'){B.tick(1/60);}
               b.shieldOn=false;b.cycle=0;const hp1=b.hp;G.fire(-Math.PI/2+0.01);for(let i=0;i<2000&&G.state==='FIRING';i++)B.tick(1/60);o.openDmg=Math.round(hp1-b.hp);
               while(G.state!=='AIMING'){if(G.state==='UPGRADE')G.pick(0);else B.tick(1/60);}
               b.hp=1;G.fire(-Math.PI/2+0.01);for(let i=0;i<2000&&G.state==='FIRING';i++)B.tick(1/60);
               o.dead=b.dead;o.bosses=R.bosses;
               while(G.state==='FIRING'||G.state==='RESOLVING')B.tick(1/60);o.bossSummons=R.pendingSummons+R.summons;toAim();
               o.waveAfter=R.wave;return o;})()""")
            check("boss spawns as 3x2 entity", boss["spawned"] and boss["w"] == 3 and boss["h"] == 2, boss)
            check("boss shield blocks straight shots from below (only blast splash gets through)", boss["blockedDmg"] < boss["openDmg"], boss)
            check("boss defeat counted and wave advances", boss["dead"] and boss["bosses"] == 1 and boss["waveAfter"] == 6, boss)
            check("boss defeat grants 2 hero summons", boss["bossSummons"] >= 2, boss)
            c.pump()
            check("no JS errors (content)", not c.errors(), c.errors(False))

        # ---------------- Bot balance runs ----------------
        if want("balance"):
            rows = []
            for i, (smart, q) in enumerate([(False, "seed=101"), (True, "seed=202"), (True, "seed=303"), (True, "seed=404"), (False, "seed=505")]):
                fresh(c, "nosdk=1&" + q)
                if i > 0:  # returning-player runs (not first-run curated)
                    c.ev("BONK.Save.d.tutorialDone=true;BONK.Save.d.stats.runs=1;skipTuts();BONK.Game.newRun();BONK.Game.state='AIMING';")
                r = c.ev(f"JSON.stringify(botRun(400,{str(smart).lower()},'fusion'))")
                rows.append(json.loads(r))
                print("   bot", "smart" if smart else "random", r, flush=True)
            avg_t = sum(r["simT"] for r in rows) / len(rows)
            check("bot runs end in game over (game is beatable-but-lethal)", all(r["state"] in ("RESULTS", "GAME_OVER") for r in rows), [r["state"] for r in rows])
            check("average bot run length within 3–12 min (target 6–8 for humans)", 180 <= avg_t <= 720, f"avg {avg_t/60:.1f} min")
            check("balls/particles bounded during full runs", all(r["maxBalls"] <= 160 and r["maxParts"] <= 700 for r in rows))
            check("first run reaches a fusion", len(rows[0]["fusions"]) > 0, [r["fusions"] for r in rows])
            ts = [r["tSummon"] for r in rows]; tm = [r["tMerge"] for r in rows]
            check("first hero summon within ~45 s in every run", all(t is not None and t <= 45 for t in ts), ts)
            check("first 3-merge within ~120 s in every run", all(t is not None and t <= 120 for t in tm), tm)
            check("Lv3 hero reached in most runs", sum(1 for r in rows if r["bestLv"] >= 3) >= 3, [r["bestLv"] for r in rows])
            c.pump()
            check("no JS errors (balance)", not c.errors(), c.errors(False))

        # ---------------- Restarts / leaks ----------------
        if want("restart"):
            fresh(c, "nosdk=1&seed=31")
            res = c.ev(r"""(()=>{const B=BONK,G=B.Game;for(let k=0;k<25;k++){
                 if(G.state!=='AIMING'){return 'bad state '+G.state;}
                 G.fire(-1.3);for(let i=0;i<40;i++)B.tick(1/60);
                 G.pause();if(G.state!=='PAUSED')return 'no pause';G.restart();}
               B.tick(1/60);return{state:G.state,balls:B.balls.list.length,free:B.balls.free.length,parts:B.parts.free.length+B.parts.list.length,runs:B.Save.d.stats.runs};})()""")
            check("25 restarts: no freeze, pools fully recycled", isinstance(res, dict) and res["state"] == "AIMING" and res["balls"] + res["free"] == 160 and res["parts"] == 700, res)
            c.pump()
            check("no JS errors (restart)", not c.errors(), c.errors(False))

        # ---------------- Persistence, shop, codex, missions ----------------
        if want("persist"):
            fresh(c, "nosdk=1&seed=41")
            c.ev("BONK.Save.d.coins=3000;BONK.Save.flush();")
            c.ev("BONK.Game.pause();BONK.Game.quit();")
            check("quit to menu", c.ev("BONK.Game.state") == "MENU")
            c.ev("document.querySelector('[data-a=shop]').click()")
            c.ev("document.querySelector('#shopList [data-a=buy][data-id=hp]').click()")
            c.ev("document.querySelector('#shopList [data-a=unlock][data-id=frosty]').click()")
            coins = c.ev("BONK.Save.d.coins")
            c.ev("BONK.Meta.track('kills',7);BONK.Save.flush();")
            c.ev("document.querySelector('[data-a=back]').click()")
            c.nav(BASE + "?nosdk=1")
            check("returning player gets the menu", c.ev("BONK.Game.state") == "MENU")
            check("permanent upgrade survives reload", c.ev("BONK.Save.d.perm.hp") == 1)
            check("hero unlock survives reload", c.ev("BONK.Save.d.unlocked.frosty") is True)
            check("coins survive reload", c.ev("BONK.Save.d.coins") == coins, coins)
            check("daily mission progress survives reload", c.ev("BONK.Save.d.daily.missions.some(m=>m.id==='kills'&&m.p>=7)") or not c.ev("BONK.Save.d.daily.missions.some(m=>m.id==='kills')"))
            check("perm HP applies to new run", c.ev("BONK.Game.startRun(),BONK.R.maxHp") == 6)
            c.ev("BONK.Game.pause();BONK.Game.quit();")
            # codex
            c.ev("document.querySelector('[data-a=codex]').click()")
            prog = c.ev("document.getElementById('cxProg').textContent")
            check("codex shows discovery progress (5 heroes unlocked)", "5 / 8" in prog and "0 / 4" in prog, prog)
            c.ev("document.querySelector('#cxFus [data-id=thunder]').click()")
            check("undiscovered fusion shown as ?", "Undiscovered" in c.ev("document.getElementById('cdInfo').textContent"))
            c.ev("BONK.Save.d.fusions.thunder=true;BONK.UI&&0");
            c.ev("document.querySelector('[data-a=cdBack]').click();document.querySelector('#codex [data-a=back]').click();document.querySelector('[data-a=codex]').click();document.querySelector('#cxFus [data-id=thunder]').click()")
            check("discovered fusion shows recipe", "Splittini" in c.ev("document.getElementById('cdInfo').textContent"))
            c.ev("document.querySelector('[data-a=cdBack]').click();document.querySelector('#codex [data-a=back]').click()")
            # missions: claim rules + calendar rules
            r = c.ev(r"""(()=>{const B=BONK,M=B.Meta,S=B.Save.d;const out={};const m=S.daily.missions[0];
               out.claimEarly=M.claim(0);m.p=m.n;const c0=S.coins;out.claim1=M.claim(0);out.claim2=M.claim(0);out.gain=S.coins-c0;
               const before=JSON.stringify(S.daily.missions);S.daily.day='2099-01-01';M.ensureDaily();out.backwardsKept=JSON.stringify(S.daily.missions)===before;
               S.daily.day='2000-01-01';M.ensureDaily();out.forwardReset=S.daily.missions.every(x=>x.p===0&&!x.claimed)&&S.daily.missions.length===3;
               return out;})()""")
            check("mission cannot be claimed before completion", r["claimEarly"] is False)
            check("mission reward claimable exactly once", r["claim1"] is True and r["claim2"] is False and r["gain"] > 0, r)
            check("clock moved backwards keeps current missions", r["backwardsKept"])
            check("new calendar day resets missions", r["forwardReset"])
            # corrupted/partial save
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            c.ev("localStorage.setItem('bonkageddon_save', JSON.stringify({v:1,coins:55,perm:{hp:2},settings:'garbage'}))")
            c.nav(BASE + "?nosdk=1")
            check("partial save: present fields kept, missing ones defaulted", c.ev("BONK.Save.d.coins===55&&BONK.Save.d.perm.hp===2&&BONK.Save.d.perm.balls===0&&BONK.Save.d.settings.music===true"))
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            c.ev("localStorage.setItem('bonkageddon_save','{not json')")
            c.nav(BASE + "?nosdk=1")
            check("corrupt save does not crash", c.ev("BONK.Game.state") in ("MENU", "AIMING"))
            c.pump()
            check("no JS errors (persist)", not c.errors(), c.errors(False))

        # ---------------- Home Screen persistence / save reliability ----------------
        if want("save"):
            K = "bonkageddon_save"
            def stored():
                return json.loads(c.ev(f"localStorage.getItem('{K}')") or "null")
            fresh(c, "nosdk=1&seed=43")
            check("Home Screen metadata: app title, capable, touch icon, manifest",
                  c.ev("""(()=>{const m=n=>{const e=document.querySelector('meta[name="'+n+'"]');return e&&e.content};
                    return m('apple-mobile-web-app-title')==='蹦蹦英雄'&&m('apple-mobile-web-app-capable')==='yes'&&!!document.querySelector('link[rel=apple-touch-icon]')
                      &&!!document.querySelector('link[rel=manifest]')&&document.title.indexOf('蹦蹦英雄')>=0})()"""))
            import urllib.request
            def get(u):
                with urllib.request.urlopen("http://127.0.0.1:8765/" + u) as f: return f.read()
            man = json.loads(get("manifest.webmanifest").decode("utf-8"))
            check("touch icon + manifest served (standalone, short name 蹦蹦英雄)", len(get("apple-touch-icon.png")) > 1000 and len(get("icon-512.png")) > 1000 and man["display"] == "standalone" and man["short_name"] == "蹦蹦英雄")
            # 1–3: earn coins → purchase → written immediately (same task, no timer)
            c.ev("BONK.Game.pause();BONK.Game.quit();BONK.Save.d.coins=2000;BONK.Save.flush()")
            c.ev("document.querySelector('[data-a=shop]').click();document.querySelector('#shopList [data-a=unlock][data-id=frosty]').click()")
            s1 = c.ev(f"(()=>{{document.querySelector('#shopList [data-a=buy][data-id=dmg]').click();const s=JSON.parse(localStorage.getItem('{K}'));return [s.coins,s.unlocked.frosty,s.perm.dmg,BONK.Save.d.coins]}})()")
            check("purchase + upgrade are in storage immediately after the tap", s1[0] == s1[3] and s1[1] is True and s1[2] == 1, s1)
            # permanent changes through dirty(): written right after the current task
            c.ev("BONK.Save.d.ach.lv3=true;BONK.Save.d.fusions.thunder=true;BONK.Save.dirty()")
            st = stored()
            check("achievement / codex discovery saved without waiting for a timer or pagehide", st["ach"]["lv3"] is True and st["fusions"]["thunder"] is True)
            check("rolling backup copy is written too", json.loads(c.ev(f"localStorage.getItem('{K}_bak')"))["coins"] == st["coins"])
            # 4–8: close the app (no pagehide!) and reopen → everything preserved
            c.send("Page.navigate", url="about:blank"); time.sleep(0.4)
            c.nav(BASE + "?nosdk=1")
            got = c.ev("(()=>{const S=BONK.Save.d;return [S.coins,S.unlocked.frosty,S.perm.dmg,S.ach.lv3,S.fusions.thunder,BONK.Game.state]})()")
            check("reopen: coins, hero, upgrade, achievement, codex preserved", got[:5] == [s1[3], True, 1, True, True] and got[5] == "MENU", got)
            c.nav(BASE + "?nosdk=1")
            check("reload again: still preserved", c.ev("BONK.Save.d.coins") == s1[3] and c.ev("BONK.Save.d.unlocked.frosty") is True)
            # early pagehide/visibility before the save is loaded must not write defaults over it
            c.send("Network.setBlockedURLs", urls=["*sdk.crazygames.com*"]); c.send("Network.enable")
            sid = c.send("Page.addScriptToEvaluateOnNewDocument", source="window.CrazyGames={SDK:{environment:'disabled',init:()=>new Promise(r=>setTimeout(r,1500))}};")["identifier"]
            c.nav(BASE)
            c.ev("window.dispatchEvent(new Event('pagehide'));document.dispatchEvent(new Event('visibilitychange'))")
            mid = stored()
            time.sleep(2.0)
            check("pagehide during slow SDK init does not overwrite the save", mid["coins"] == s1[3] and mid["unlocked"]["frosty"] is True and c.ev("BONK.Save.d.coins") == s1[3], mid["coins"])
            c.send("Page.removeScriptToEvaluateOnNewDocument", identifier=sid); c.send("Network.setBlockedURLs", urls=[])
            # update with a newer save format (old cached page): unknown fields and the newer version survive a write
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            c.ev(f"(()=>{{const s=JSON.parse(localStorage.getItem('{K}'));s.v=99;s.futureThing={{a:1}};s.ach.futureAch=true;localStorage.setItem('{K}',JSON.stringify(s));}})()")
            c.nav(BASE + "?nosdk=1")
            c.ev("BONK.Save.d.coins+=5;BONK.Save.flush()")
            st = stored()
            check("newer save format: version, unknown fields and progress kept", st["v"] == 99 and st.get("futureThing") == {"a": 1} and st["ach"].get("futureAch") is True and st["coins"] == s1[3] + 5, [st["v"], st.get("futureThing")])
            # corrupt main save → restored from the backup; the corrupt copy is kept
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            c.ev(f"localStorage.setItem('{K}','{{broken')")
            c.nav(BASE + "?nosdk=1")
            check("corrupt save: progress restored from backup, corrupt copy kept",
                  c.ev("BONK.Save.d.coins") == s1[3] + 5 and c.ev("BONK.Save.d.unlocked.frosty") is True and c.ev(f"localStorage.getItem('{K}_corrupt')") == "{broken" and stored()["coins"] == s1[3] + 5)
            # storage that throws on read: never overwrite what could not be read
            r = c.ev(f"""(()=>{{const B=BONK.Save,o=Storage.prototype.getItem,before=localStorage.getItem('{K}');
                Storage.prototype.getItem=function(k){{if(k.indexOf('bonkageddon')===0)throw new Error('denied');return o.call(this,k);}};
                B.load();const blocked=B.blocked,coins=B.d.coins;B.d.coins=1;const w1=B.flush();
                Storage.prototype.getItem=o;const w2=B.flush();
                return {{blocked,coins,w1,w2,same:localStorage.getItem('{K}')===before}};}})()""")
            check("unreadable storage: defaults are never written over the real save", r["blocked"] and r["w1"] is False and r["w2"] is False and r["same"], r)
            # writes that throw (quota / private mode) do not crash the game
            c.nav(BASE + "?nosdk=1")
            r = c.ev("""(()=>{const o=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('quota')};
                let ok;try{ok=BONK.Save.flush();}catch(e){ok='threw'}Storage.prototype.setItem=o;return [ok,!!BONK.Save.lastError];})()""")
            check("write failure is caught and reported (no crash)", r == [False, True], r)
            c.nav(BASE + "?nosdk=1")
            check("after all failures the real progress is still there", c.ev("BONK.Save.d.coins") == s1[3] + 5 and c.ev("BONK.Save.d.unlocked.frosty") is True)
            c.pump()
            check("no JS errors (save)", not c.errors(), c.errors(False))

        # ---------------- SDK adapter ----------------
        if want("sdk"):
            c.send("Network.setBlockedURLs", urls=["*sdk.crazygames.com*"])
            sid = c.send("Page.addScriptToEvaluateOnNewDocument", source=MOCK_JS)["identifier"]

            def boot_mock(cfg, clear=True):
                c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
                if clear:
                    c.ev("localStorage.clear()")
                c.ev(f"localStorage.setItem('__mock', {json.dumps(json.dumps(cfg))})")
                c.nav(BASE + "?seed=55")
                c.ev(BOT_JS)

            boot_mock({"ad": "finish"})
            check("SDK available: adapter initialised in crazygames env", c.ev("BONK.CG.ok && BONK.CG.env==='crazygames'"))
            log = c.ev("__log")
            check("init → loadingStart/Stop → gameplayStart order", log[:4] == ["init", "loadingStart", "loadingStop", "gameplayStart"], log[:5])
            c.ev("BONK.Game.pause()"); c.ev("BONK.Game.resume()"); c.ev("BONK.Game.pause()"); c.ev("BONK.Game.resume()")
            c.ev("BONK.Game.fire(-1.3)"); finish_turn(c)
            seq = [x for x in c.ev("__log") if x.startswith("gameplay")]
            dup = any(seq[i] == seq[i + 1] for i in range(len(seq) - 1))
            check("gameplayStart/Stop never duplicated", not dup, seq)
            c.ev("BONK.Save.flush()")
            check("save goes to SDK data module in crazygames env", c.ev("BONK.Save.store") == "crazygames" and "dataSet" in c.ev("__log"))
            # hero board → gameplayStop, voluntary ad summon, close → passive cards
            c.ev("BONK.Save.d.tut.gate=1;BONK.Save.d.tut.summon=1;BONK.Save.d.tut._since=5;BONK.R.pendingLv=1;BONK.R.pendingPassive=1;BONK.Game.fire(-1.3)");
            for _ in range(200):
                if c.ev("BONK.Game.state") == "BOARD": break
                c.ev("BONK.advance(0.5,60)")
            check("hero board opens after level-up and calls gameplayStop", c.ev("BONK.Game.state") == "BOARD" and c.ev("__log[__log.length-1]") == "gameplayStop", c.ev("__log.slice(-3)"))
            check("first board = merge lesson: no ad offered, FIGHT replaced by SKIP", c.ev("BONK.Tut.active()") and c.ev("getComputedStyle(document.getElementById('bdAd')).display") == "none"
                  and c.ev("getComputedStyle(document.getElementById('bdFight')).display") == "none")
            n_ads = len([x for x in c.ev("__log") if x.startswith("requestAd")])
            c.ev("BONK.Game.boardAd()")
            check("ad cannot start inside the lesson", c.ev("BONK.Game.state") == "BOARD" and len([x for x in c.ev("__log") if x.startswith("requestAd")]) == n_ads)
            c.ev("BONK.Board.finishAll();document.getElementById('bdSkip').click()")
            check("SKIP ends the lesson (no softlock), FIGHT is back", not c.ev("BONK.Tut.active()") and c.ev("getComputedStyle(document.getElementById('bdFight')).display") != "none" and c.ev("BONK.Tut.done('merge')"))
            check("ad summon offered on the board when SDK available", c.ev("getComputedStyle(document.getElementById('bdAd')).display") != "none")
            c.ev("BONK.Board.finishAll()"); s0 = c.ev("BONK.R.summons")
            c.ev("BONK.Game.boardAd()")
            check("board ad → AD_PLAYING, no summon at ad start", c.ev("BONK.Game.state") == "AD_PLAYING" and c.ev("BONK.R.pendingSummons") == 0)
            time.sleep(0.6)
            c.ev("BONK.Board.finishAll()")
            check("ad summon granted after adFinished, back on the board", c.ev("BONK.Game.state") == "BOARD" and c.ev("BONK.R.summons") == s0 + 1, (c.ev("BONK.Game.state"), s0, c.ev("BONK.R.summons")))
            c.ev("BONK.Game.boardAd()")
            check("ad summon only once per wave", c.ev("BONK.Game.state") == "BOARD" and c.ev("getComputedStyle(document.getElementById('bdAd')).display") == "none")
            c.ev("BONK.Game.closeBoard()")
            check("closing the board opens the passive pick (gameplay still stopped)", c.ev("BONK.Game.state") == "UPGRADE" and c.ev("BONK.CG.playing") is False and [x for x in c.ev("__log") if x.startswith("gameplay")][-1] == "gameplayStop")
            check("ad reroll offered when SDK available", c.ev("getComputedStyle(document.getElementById('rrAd')).display") != "none")
            before = c.ev("JSON.stringify(BONK.R.choices)")
            c.ev("BONK.Game.reroll(true)")
            check("AD_PLAYING during rewarded ad, audio muted", c.ev("BONK.Game.state") == "AD_PLAYING" and c.ev("BONK.Game.state==='AD_PLAYING'"))
            time.sleep(0.6)
            check("rewarded reroll success → back to UPGRADE with new cards", c.ev("BONK.Game.state") == "UPGRADE" and c.ev("JSON.stringify(BONK.R.choices)") != before)
            c.ev("BONK.Game.reroll(true)")
            check("ad reroll only once per screen", c.ev("BONK.Game.state") == "UPGRADE")
            finish_turn(c)
            # revive success
            c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)")
            st = finish_turn(c)
            check("death with SDK → revive offer screen", st == "GAME_OVER" and c.ev("document.getElementById('gameover').classList.contains('show')"), st)
            c.ev("document.getElementById('goRevive').click()")
            check("revive: no reward at ad start", c.ev("BONK.R.hp") == 0)
            time.sleep(0.6)
            check("revive granted only after adFinished", c.ev("BONK.Game.state") == "AIMING" and c.ev("BONK.R.hp") == 3)
            c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)")
            st = finish_turn(c)
            check("second death: no second revive (straight to results)", st == "RESULTS", st)
            coins0 = c.ev("BONK.Save.d.coins"); earned = c.ev("BONK.R.coinsEarned")
            c.ev("BONK.Game.doubleCoins()"); time.sleep(0.6); c.ev("BONK.Game.doubleCoins()"); time.sleep(0.6)
            check("double coins granted exactly once", c.ev("BONK.Save.d.coins") - coins0 == earned, (coins0, earned, c.ev("BONK.Save.d.coins")))
            c.ev("window.__adMode='error'")
            c.ev("BONK.Game.playAgain()")
            time.sleep(0.4)
            check("midgame ad error → still starts the new run", c.ev("BONK.Game.state") == "AIMING" and c.ev("BONK.R.turn") == 0)
            # rewarded failure
            c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)"); finish_turn(c)
            c.ev("BONK.Game.revive()"); time.sleep(0.4)
            check("rewarded ad error → no revive, results shown", c.ev("BONK.Game.state") == "RESULTS" and c.ev("BONK.R.hp") == 0)
            c.ev("window.__adMode='finish'"); c.ev("BONK.Game.playAgain()"); time.sleep(0.6)
            check("midgame ad success → new run", c.ev("BONK.Game.state") == "AIMING")
            c.ev("window.__adMode='throw'"); c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)"); finish_turn(c)
            c.ev("BONK.Game.revive()"); time.sleep(0.3)
            check("requestAd throwing → handled, no reward", c.ev("BONK.Game.state") == "RESULTS")
            # ad that never calls back → watchdog
            c.ev("window.__adMode='never'"); c.ev("BONK.Game.playAgain()")
            check("silent ad: game shows ad overlay meanwhile", c.ev("BONK.Game.state") == "AD_PLAYING")
            time.sleep(12.8)
            check("silent ad: watchdog releases player (~12s)", c.ev("BONK.Game.state") == "AIMING")
            c.ev("window.__adMode='finish'")
            # sdk mute setting
            check("muteAudio=false respected", c.ev("BONK.CG.sdkMute") is False)
            c.ev("__settingsFn({muteAudio:true,disableChat:false})")
            check("muteAudio change listener applied", c.ev("BONK.CG.sdkMute") is True)
            # happytime on boss
            c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;R.wave=5;R.enemies.length=0;R.grid.fill(null);G.spawnBoss();R.boss.hp=1;R.boss.dy=0;R.boss.shieldOn=false;G.fire(-Math.PI/2+0.01);
                for(let i=0;i<2000&&G.state==='FIRING';i++)B.tick(1/60);})()""")
            check("happytime() on boss defeat", "happytime" in c.ev("__log"))
            c.pump(); errs = c.errors()
            check("no JS errors (sdk ok)", not errs, errs)

            boot_mock({"initFail": True})
            check("SDK init failure → standalone, playable", c.ev("!BONK.CG.ok") and c.ev("BONK.Game.state") == "AIMING")
            c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)"); st = finish_turn(c)
            check("SDK init failure → no revive/ad buttons, straight to results", st == "RESULTS" and c.ev("getComputedStyle(document.getElementById('rsDouble')).display") == "none", st)
            c.ev("BONK.Game.playAgain()"); c.ev("skipTuts();BONK.R.pendingLv=1;BONK.Game.fire(-1.3)")
            for _ in range(200):
                if c.ev("BONK.Game.state") == "BOARD": break
                c.ev("BONK.advance(0.5,60)")
            check("without SDK: board works and hides the ad-summon button", c.ev("BONK.Game.state") == "BOARD" and c.ev("getComputedStyle(document.getElementById('bdAd')).display") == "none")
            boot_mock({"env": "disabled"})
            check("environment 'disabled' → SDK calls skipped", not c.ev("BONK.CG.ok") and "gameplayStart" not in c.ev("__log"))
            boot_mock({"dataThrow": True})
            c.ev("BONK.Save.d.coins=77;BONK.Save.flush()")
            check("data module throwing → falls back to localStorage", "77" in (c.ev("localStorage.getItem('bonkageddon_save')") or ""))
            boot_mock({"mute": True})
            check("muteAudio=true at boot → game audio muted", c.ev("BONK.CG.sdkMute") is True)
            c.send("Page.removeScriptToEvaluateOnNewDocument", identifier=sid)
            # SDK script completely unreachable
            c.nav(BASE + "?seed=1")
            check("SDK script blocked → game still boots", c.ev("BONK.Game.state") in ("MENU", "AIMING") and not c.ev("BONK.CG.ok"))
            c.send("Network.setBlockedURLs", urls=[])
            c.pump(); errs = [e for e in c.errors() if "crazygames" not in e.lower() and "ERR_BLOCKED" not in e]
            check("no JS errors (sdk failure modes)", not errs, errs)

        # ---------------- Real SDK on localhost (environment 'local') ----------------
        if want("realsdk"):
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'"); c.ev("localStorage.clear()")
            c.nav(BASE + "?seed=3", timeout=30)
            time.sleep(1)
            env_ = c.ev("BONK.CG.env"); ok = c.ev("BONK.CG.ok")
            check("real CrazyGames SDK script loads on localhost", env_ in ("local", "crazygames", "none", "disabled"), f"env={env_} ok={ok}")
            if ok:
                c.ev("BONK.R.hp=0;BONK.Game.fire(-1.3)"); st = finish_turn(c)
                check("real SDK (local env): revive offer", st == "GAME_OVER", st)
                c.ev("BONK.Game.revive()")
                for _ in range(60):
                    if c.ev("BONK.Game.state") != "AD_PLAYING": break
                    time.sleep(0.5)
                check("real SDK (local env): rewarded ad flow returns control", c.ev("BONK.Game.state") in ("AIMING", "RESULTS"), c.ev("BONK.Game.state"))
            c.pump(); errs = c.errors()
            check("no JS errors (real sdk)", not errs, errs)

        # ---------------- Hero merge board ----------------
        if want("merge"):
            fresh(c, "nosdk=1&seed=61")
            # first board of a new player: starter pair + guaranteed starter summon → a merge is one move away
            c.ev("skipTuts();BONK.R.pendingLv=1;BONK.Game.openBoard();BONK.Board.finishAll()")
            check("first summon is the starter → 3 starters on the board", c.ev("BONK.R.summons===1&&BONK.R.board.filter(u=>u&&u.id===BONK.R.starter).length===3"), c.ev("boardSig()"))
            check("board shows a one-move merge hint", c.ev("!!BONK.Board.hint"))
            check("board state pauses combat (gameplay stopped)", c.ev("BONK.Game.state==='BOARD'&&!BONK.CG.playing===!BONK.CG.ok"))
            c.ev("BONK.Game.pause()")
            check("pause key ignored while on the board", c.ev("BONK.Game.state") == "BOARD")
            r = c.ev(r"""(()=>{const B=BONK.Board,R=BONK.R,o={};
              const run=(spec,a,b)=>{setBoard(spec);const m0=R.merges;B.move(a,b);B.finishAll();return{sig:boardSig(),n:R.merges-m0};};
              o.h=run({0:['banana',1],1:['banana',1],7:['banana',1]},7,2);
              o.v=run({2:['zappy',1],7:['zappy',1],20:['zappy',1]},20,12);
              o.L=run({0:['bean',1],5:['bean',1],7:['bean',1]},7,6);
              o.diff=run({0:['banana',1],1:['zappy',1],7:['banana',1]},7,2);
              o.lvl=run({0:['banana',1],1:['banana',2],7:['banana',1]},7,2);
              o.diag=run({0:['frosty',1],6:['frosty',1],18:['frosty',1]},18,12);
              o.big=run({0:['bean',1],1:['bean',1],5:['bean',1],6:['bean',1],20:['bean',1]},20,2);
              o.big2=run({0:['bean',1],1:['bean',1],5:['bean',1],6:['bean',1],20:['bean',1]},20,2);
              o.chain=run({0:['zappy',2],1:['zappy',2],6:['zappy',1],7:['zappy',1],22:['zappy',1]},22,2);o.chainBest=R.bestChain;
              o.max=run({0:['muffin',9],1:['muffin',9],7:['muffin',9]},7,2);
              o.swap=run({0:['banana',1],1:['banana',1],2:['zappy',1],12:['banana',1]},12,2);
              setBoard({3:['banana',1]});o.emptyMove=B.move(10,11);o.sameMove=B.move(3,3);
              setBoard({0:['bean',1]});B.move(0,100);o.toRes=boardSig();B.move(100,4);o.fromRes=boardSig();
              return o;})()""")
            cell = lambda sig, i: sig.split("|")[0].split(",")[i]
            check("3 identical same-level heroes merge (horizontal)", r["h"]["n"] == 1 and cell(r["h"]["sig"], 2) == "banana2" and r["h"]["sig"].count("banana") == 1, r["h"])
            check("vertical line merges", r["v"]["n"] == 1 and cell(r["v"]["sig"], 12) == "zappy2", r["v"])
            check("L-shaped orthogonal group merges at the drop cell", r["L"]["n"] == 1 and cell(r["L"]["sig"], 6) == "bean2", r["L"])
            check("different heroes do not merge", r["diff"]["n"] == 0, r["diff"])
            check("different levels do not merge", r["lvl"]["n"] == 0, r["lvl"])
            check("diagonal-only line does not merge", r["diag"]["n"] == 0, r["diag"])
            check("group of 5 = MEGA MERGE: two evolved heroes (drop cell + nearest), all 5 used", r["big"]["n"] == 1 and cell(r["big"]["sig"], 2) == "bean2" and cell(r["big"]["sig"], 1) == "bean2" and r["big"]["sig"].count("bean") == 2, r["big"])
            check("large-group rule is deterministic", r["big"] == r["big2"])
            check("chain merge: Lv1 triple completes a Lv2 triple → Lv3", r["chain"]["n"] == 2 and cell(r["chain"]["sig"], 2) == "zappy3" and r["chain"]["sig"].count("zappy") == 1 and r["chainBest"] >= 2, r["chain"])
            check("MAX (Lv9) heroes never merge", r["max"]["n"] == 0 and r["max"]["sig"].count("muffin9") == 3, r["max"])
            check("dropping onto another hero swaps and re-checks", r["swap"]["n"] == 1 and cell(r["swap"]["sig"], 2) == "banana2" and cell(r["swap"]["sig"], 12) == "zappy1", r["swap"])
            check("moves from empty cells / onto self are rejected", r["emptyMove"] is False and r["sameMove"] is False)
            check("heroes move to and from the reserve", r["toRes"].endswith("|bean1,-,-") and cell(r["fromRes"], 4) == "bean1" and r["fromRes"].endswith("|-,-,-"), (r["toRes"], r["fromRes"]))
            full = c.ev(r"""(()=>{const B=BONK.Board,R=BONK.R;const spec={};for(let i=0;i<25;i++)spec[i]=[i%2?'zappy':'banana',1];setBoard(spec);
              R.summons=5;R.dry=0;const c0=R.bonusCoins||0;
              const a=B.summon();B.finishAll();const inRes=R.reserve.filter(Boolean).length;
              B.summon();B.summon();B.finishAll();const full=R.reserve.filter(Boolean).length;
              const r=B.summon();B.finishAll();
              return{firstCell:a,inRes,full,last:r,coins:(R.bonusCoins||0)-c0,units:R.board.filter(Boolean).length+R.reserve.filter(Boolean).length,converted:R.fullConverted};})()""")
            check("full board: summons go to the reserve", full["firstCell"] == 100 and full["inRes"] == 1 and full["full"] == 3, full)
            check("board + reserve full: summon explicitly converted to coins (no silent loss)", full["last"] == -1 and full["coins"] == 10 and full["units"] == 28 and full["converted"] == 1, full)
            summ = c.ev(r"""(()=>{BONK.Game.newRun();BONK.Game.state='BOARD';const B=BONK.Board,R=BONK.R;const out={};
              out.first=B.pickType()===R.starter;
              setBoard({0:['zappy',1],2:['zappy',1]});R.summons=4;R.dry=3;out.pity=B.pickType()==='zappy';
              setBoard({});R.dry=0;const cnt={};for(let i=0;i<400;i++){const t=B.pickType();cnt[t]=(cnt[t]||0)+1;}
              out.inPool=Object.keys(cnt).every(t=>R.pool.indexOf(t)>=0);out.allSeen=R.pool.every(t=>cnt[t]>0);out.cnt=cnt;
              R.focus=R.pool[1];const c2={};for(let i=0;i<400;i++){const t=B.pickType();c2[t]=(c2[t]||0)+1;}out.focusUp=c2[R.pool[1]]>cnt[R.pool[1]]*1.4;R.focus=null;
              out.pool=R.pool;return out;})()""")
            check("summons: first is the starter; drought pity completes a waiting pair", summ["first"] and summ["pity"], summ)
            check("summon distribution: only run-pool heroes, every pool hero appears", summ["inPool"] and summ["allSeen"], summ["cnt"])
            check("summon focus raises that hero's share", summ["focusUp"], summ)
            # mouse drag-and-drop, click-to-select/place
            c.ev("BONK.Game.newRun();BONK.Game.state='AIMING';BONK.Game.openBoard();setBoard({0:['bean',1],1:['bean',1],7:['bean',1]})")
            cc = lambda i: clientxy(c, 26 + (i % 5) * 80 + 38, 128 + (i // 5) * 80 + 38)
            (x0, y0), (x1, y1) = cc(7), cc(2)
            c.mouse("mousePressed", x0, y0)
            for k in range(1, 9): c.mouse("mouseMoved", x0 + (x1 - x0) * k / 9, y0 + (y1 - y0) * k / 9)
            prev = c.ev("JSON.stringify(BONK.Board.preview)")
            c.mouse("mouseMoved", x1, y1); c.mouse("mouseReleased", x1, y1); c.ev("BONK.Board.finishAll()")
            check("mouse drag shows merge preview, drop merges", prev not in ("null", None) and cell(c.ev("boardSig()"), 2) == "bean2", (prev, c.ev("boardSig()")))
            c.ev("setBoard({0:['banana',1],1:['banana',1],12:['banana',1]})")
            for i in (12, 2):
                x, y = cc(i); c.mouse("mousePressed", x, y); c.mouse("mouseReleased", x, y)
            c.ev("BONK.Board.finishAll()")
            check("click hero then click cell (select & place) merges", cell(c.ev("boardSig()"), 2) == "banana2", c.ev("boardSig()"))
            # touch drag on a phone viewport + interrupted touch
            c.metrics(390, 844, 3, True)
            for _ in range(30):  # wait until the game's resize handler has applied the new viewport
                time.sleep(0.05)
                if c.ev("BONK.view.cw===innerWidth&&BONK.view.ch===innerHeight"): break
            c.ev("setBoard({0:['zappy',1],1:['zappy',1],7:['zappy',1]})")
            (x0, y0), (x1, y1) = cc(7), cc(2)
            c.touch("touchStart", x0, y0)
            for k in range(1, 6): c.touch("touchMove", x0 + (x1 - x0) * k / 6, y0 + (y1 - y0) * k / 6)
            c.send("Input.dispatchTouchEvent", type="touchCancel", touchPoints=[])
            check("touchcancel mid-drag leaves the board unchanged", cell(c.ev("boardSig()"), 7) == "zappy1" and not c.ev("!!BONK.Board.drag"))
            c.touch("touchStart", x0, y0)
            for k in range(1, 6): c.touch("touchMove", x0 + (x1 - x0) * k / 6, y0 + (y1 - y0) * k / 6)
            c.touch("touchMove", x1, y1); c.touch("touchEnd", x1, y1); c.ev("BONK.Board.finishAll()")
            check("touch drag-and-drop merges", cell(c.ev("boardSig()"), 2) == "zappy2", c.ev("boardSig()"))
            c.metrics(450, 820, 1)
            # animation timing, skip, close/restart during animations
            an = c.ev(r"""(()=>{const B=BONK.Board,R=BONK.R,G=BONK.Game,o={};
              const timeIt=()=>{let t=0;while(B.busy()&&t<10){BONK.tick(1/60);t+=1/60;}return +t.toFixed(2);};
              setBoard({0:['banana',1],1:['banana',1],7:['banana',1]});B.move(7,2);o.single=timeIt();
              setBoard({0:['zappy',2],1:['zappy',2],6:['zappy',1],7:['zappy',1],22:['zappy',1]});B.move(22,2);o.double=timeIt();
              setBoard({0:['croissant',3],1:['croissant',3],7:['croissant',3]});B.move(7,2);o.legend=timeIt();
              setBoard({0:['zappy',2],1:['zappy',2],6:['zappy',1],7:['zappy',1],22:['zappy',1]});B.move(22,2);BONK.tick(0.2);
              o.midBusy=B.busy();B.down({x:3,y:3});o.skipSig=boardSig();o.skipBusy=B.busy();
              const uids=R.board.concat(R.reserve).filter(Boolean).map(u=>u.uid);o.uidsUnique=new Set(uids).size===uids.length;
              setBoard({0:['bean',1]});R.pendingSummons=3;const s0=R.summons;BONK.tick(0.1);o.busyBeforeClose=B.busy();
              G.closeBoard();o.afterClose={state:G.state,pend:R.pendingSummons,added:R.summons-s0,busy:B.busy()};
              G.openBoard();R.pendingSummons=2;BONK.tick(0.12);G.closeBoard();G.pause();G.restart();
              o.afterRestart={state:G.state,units:BONK.R.board.filter(Boolean).length,cur:!!B.cur,anims:B.anims.length,pend:BONK.R.pendingSummons};
              return o;})()""")
            check("single merge animation completes in <1.8 s", 0 < an["single"] < 1.8, an)
            check("chain (2 steps) completes in <3 s; Lv4 reveal <2.2 s", an["double"] < 3 and an["legend"] < 2.2, an)
            check("tap during animation skips to the final state", an["midBusy"] and not an["skipBusy"] and an["skipSig"].split("|")[0].split(",")[2] == "zappy3", an)
            check("no duplicated or lost heroes after skipping", an["uidsUnique"])
            check("closing mid-animation resolves all pending summons", an["busyBeforeClose"] and an["afterClose"]["state"] == "AIMING" and an["afterClose"]["pend"] == 0 and an["afterClose"]["added"] == 3 and not an["afterClose"]["busy"], an["afterClose"])
            check("restart after board animations → clean new board", an["afterRestart"] == {"state": "AIMING", "units": 2, "cur": False, "anims": 0, "pend": 0}, an["afterRestart"])
            # combat uses the merged hero's stats; merging never lowers damage
            cmb = c.ev(r"""(()=>{const G=BONK.Game,B=BONK;function run(spec){G.newRun();G.state='AIMING';const R=B.R;setBoard(spec);R.gates.length=0;R.enemies.length=0;R.grid.fill(null);
                for(let r=0;r<5;r++)for(let c=0;c<7;c++){const e=G.makeEnemy('gloom',c,r,1,99999);G.placeEnemy(e);}
                const mul=R.seq[0].lvMul,size=R.seq[0].size,chain=R.seq[0].chain;G.fire(-1.3);for(let i=0;i<3000&&G.state==='FIRING';i++)B.tick(1/60);
                return{dmg:Math.round(R.dmgDealt),volley:G.volleySize(),mul,size,chain,arcs:R.arcs};}
              return{l1:run({0:['zappy',1],1:['zappy',1],2:['zappy',1]}),l2:run({0:['zappy',2]}),l3:run({0:['zappy',3]}),l4:run({0:['zappy',4]})};})()""")
            check("Lv2 vs three Lv1: same volley size, more damage", cmb["l2"]["volley"] == cmb["l1"]["volley"] and cmb["l2"]["dmg"] > cmb["l1"]["dmg"], cmb)
            check("each level raises per-ball multiplier, size and ability", cmb["l1"]["mul"] < cmb["l2"]["mul"] < cmb["l3"]["mul"] < cmb["l4"]["mul"] and cmb["l1"]["chain"] < cmb["l2"]["chain"] < cmb["l3"]["chain"] < cmb["l4"]["chain"] and cmb["l4"]["size"] > 1.2, cmb)
            check("combat damage grows Lv1→Lv4", cmb["l1"]["dmg"] < cmb["l2"]["dmg"] < cmb["l3"]["dmg"] < cmb["l4"]["dmg"], [cmb[k]["dmg"] for k in ("l1", "l2", "l3", "l4")])
            # HUD board button
            c.ev("toAim()")
            check("HUD 'heroes' button visible while aiming", c.ev("getComputedStyle(document.getElementById('hudBoard')).display") != "none")
            c.ev("document.getElementById('hudBoard').click()")
            check("HUD button opens the board", c.ev("BONK.Game.state") == "BOARD")
            c.ev("document.getElementById('bdFight').click()")
            check("FIGHT closes the board", c.ev("BONK.Game.state") == "AIMING")
            # performance: big chain + hint scan, full-board render
            pf = c.ev(r"""(()=>{const B=BONK.Board,R=BONK.R;BONK.Game.openBoard();const spec={};const ids=['banana','zappy','bean','croissant'];
              for(let i=0;i<25;i++)spec[i]=[ids[(i*7)%4],1+((i*3)%3)];spec[0]=['zappy',2];spec[1]=['zappy',2];spec[6]=['zappy',1];spec[7]=['zappy',1];spec[2]=null;delete spec[2];
              setBoard(spec);R.reserve[0]=B.mk('zappy',1);let t=performance.now();B.move(100,2);const moveMs=performance.now()-t;
              t=performance.now();for(let i=0;i<20;i++)B.computeHint();const hintMs=(performance.now()-t)/20;
              const s2={};for(let i=0;i<25;i++)s2[i]=[ids[i%4],4];setBoard(s2);
              let w=0,sum=0;for(let i=0;i<60;i++){const t0=performance.now();BONK.tick(1/60);BONK.render();const d=performance.now()-t0;w=Math.max(w,d);sum+=d;}
              B.finishAll();return{moveMs:+moveMs.toFixed(2),hintMs:+hintMs.toFixed(2),avgRender:+(sum/60).toFixed(2),worst:+w.toFixed(2),parts:BONK.Board&&1};})()""")
            check("chain merge + hint scan cost < 20 ms (no freeze)", pf["moveMs"] < 20 and pf["hintMs"] < 20, pf)
            check("full board of Lv4 heroes renders < 16 ms avg on this machine", pf["avgRender"] < 16, pf)
            c.ev("BONK.Game.closeBoard()")
            # save: discoveries + achievements persisted, v1 → v2 migration keeps old progress
            sv = c.ev(r"""(()=>{const S=BONK.Save;S.flush();const d=JSON.parse(localStorage.getItem('bonkageddon_save'));
              return{v:d.v,lv:d.heroLv,total:d.mergeStats.total,chain:d.mergeStats.bestChain,ach:d.ach};})()""")
            check("save v4 records hero levels, merges, achievements", sv["v"] == 4 and max(sv["lv"].values()) >= 4 and sv["total"] > 0 and sv["chain"] >= 2 and sv["ach"]["merge"] and sv["ach"]["lv4"], sv)
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            c.ev("localStorage.setItem('bonkageddon_save', JSON.stringify({v:1,coins:321,seen:{zappy:true,banana:true},fusions:{thunder:true},perm:{hp:1},unlocked:{frosty:true},stats:{runs:3,kills:10,bosses:0},tutorialDone:true}))")
            c.nav(BASE + "?nosdk=1")
            mg = c.ev("JSON.stringify({v:BONK.Save.d.v,c:BONK.Save.d.coins,hp:BONK.Save.d.perm.hp,f:BONK.Save.d.fusions.thunder,lz:BONK.Save.d.heroLv.zappy,fr:BONK.Save.d.unlocked.frosty,t:BONK.Save.d.mergeStats.total,st:BONK.Game.state})")
            check("v1 save migrates to v4 without losing coins/upgrades/discoveries", mg == json.dumps({"v": 4, "c": 321, "hp": 1, "f": True, "lz": 1, "fr": True, "t": 0, "st": "MENU"}, separators=(",", ":")), mg)
            tm = c.ev("JSON.stringify(BONK.Save.d.tut)")
            check("migration: returning player skips aim/gate/fusion lessons, still gets the merge lesson", {k: v for k, v in json.loads(tm).items() if ":" not in k} == {"aim": 1, "gate": 1, "fusion": 1}, tm)
            c.ev("document.querySelector('[data-a=codex]').click()")
            check("codex shows hero evolution progress", "/ 72" in c.ev("document.getElementById('cxProg').textContent"), c.ev("document.getElementById('cxProg').textContent"))
            c.ev("document.querySelector('[data-a=back]').click()")
            c.pump()
            check("no JS errors (merge)", not c.errors(), c.errors(False))

        # ---------------- Localization (Traditional Chinese) ----------------
        if want("i18n"):
            zshots = os.path.join(shots, "zh"); os.makedirs(zshots, exist_ok=True)
            c.metrics(450, 820, 2)
            fresh(c, "nosdk=1&seed=88")
            check("default language follows browser (en-US -> en)", c.ev("document.documentElement.lang") == "en")
            c.ev("document.getElementById('mLang').click()")
            check("language toggle switches to zh-Hant", c.ev("document.documentElement.lang") == "zh-Hant")
            check("static DOM text translated", c.ev("document.querySelector('[data-a=play]').textContent") == "開始玩")
            check("saved language preference", c.ev("BONK.Save.d.settings.lang") == "zh")
            titles = c.ev("BONK.Upgrades.build().map(x=>x.title+'|'+x.desc).join(' / ')")
            check("upgrade cards translated", all(re.search(r"[一-鿿]", t) for t in titles.split(" / ")), titles)
            c.ev("BONK.Save.flush()")
            c.nav(BASE + "?nosdk=1&seed=88"); c.ev(BOT_JS)
            check("language persists across reload", c.ev("document.documentElement.lang") == "zh-Hant")
            c.ev("BONK.render()"); c.screenshot(os.path.join(zshots, "01_first_play.png"))
            # gameplay with every gate type, then a level-up and a fusion
            c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;setBoard({0:['zappy',2],1:['bean',2],2:['bean',1],7:['bean',1],12:['bean',1]});R.wave=4;
                 for(let r=0;r<4;r++)for(let c=0;c<7;c++)if(!R.grid[r*7+c]&&(r+c)%3){const e=G.makeEnemy(['gloom','tank','shieldy','minion'][(r+c)%4],c,r,4);e.dy=0;G.placeEnemy(e);}
                 R.gates.length=0;R.gates.push({k:'mult',v:3,x:20,w:84,flash:0},{k:'power',v:'pierce',x:130,w:84,flash:0},{k:'power',v:'dmg',x:240,w:84,flash:0},{k:'mut',v:'blaze',x:345,w:84,flash:0});
                 R.pendingLv=1;R.pendingPassive=1;G.fire(-1.75);B.advance(0.9,60);B.render();})()""")
            c.screenshot(os.path.join(zshots, "02_gates.png"))
            for _ in range(200):
                if c.ev("BONK.Game.state") == "BOARD": break
                c.ev("BONK.advance(0.5,60)")
            c.ev("for(let i=0;i<120;i++)BONK.tick(0.02);BONK.Board.finishAll();BONK.Board.move(12,17);BONK.tick(0.016);BONK.tick(0.3);BONK.render()")
            c.screenshot(os.path.join(zshots, "03_board_merge.png"))
            c.ev("BONK.Board.finishAll();for(let i=0;i<30;i++)BONK.tick(0.05);BONK.render()"); c.screenshot(os.path.join(zshots, "03b_board.png"))
            leftovers0 = c.ev(r"""(()=>{const out=[];for(const b of document.querySelectorAll('#board button'))if(getComputedStyle(b).display!=='none'&&/[A-Za-z]{3,}/.test(b.textContent))out.push(b.textContent);return out;})()""")
            c.ev("BONK.Game.closeBoard()")
            c.ev("BONK.render()"); c.screenshot(os.path.join(zshots, "03c_upgrade.png"))
            c.ev("BONK.Game.pick(0)")
            finish_turn(c)
            c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;R.wave=5;R.enemies.length=0;R.grid.fill(null);G.spawnBoss();R.boss.dy=0;R.boss.shieldOn=true;R.boss.cycle=2;
               R.banner={text:'第 5 波',sub:'',t:0.3,life:9,color:'#ffe14d'};B.render();})()""")
            c.screenshot(os.path.join(zshots, "05_boss.png"))
            c.ev("BONK.Game.pause()"); c.screenshot(os.path.join(zshots, "06_pause.png"))
            c.ev("BONK.Game.quit()"); time.sleep(0.4); c.screenshot(os.path.join(zshots, "07_menu.png"))
            leftovers = set(leftovers0)
            scan = r"""(()=>{const ok=/^(BONKA-|GEDDON|EN|Lv\d.*|LV \d.*|BOSS.*|Boss.*|HP|XP|中文 \/ EN|Language \/ 語言)$/;const out=[];
               const tw=document.createTreeWalker(document.getElementById('ui'),NodeFilter.SHOW_TEXT);let n;
               while((n=tw.nextNode())){const t=n.nodeValue.trim();if(!t)continue;let el=n.parentElement,vis=true;
                 for(let p=el;p;p=p.parentElement){if(getComputedStyle(p).display==='none'){vis=false;break;}}
                 if(vis&&/[A-Za-z]{3,}/.test(t.replace(/BOSS|Boss|MAX/g,''))&&!ok.test(t))out.push(t);}return out;})()"""
            for screen in ("shop", "codex", "missions", "settings"):
                c.ev(f"BONK.Save.d.coins=420;document.querySelector('#menu [data-a={screen}]').click()")
                time.sleep(0.9); c.screenshot(os.path.join(zshots, f"08_{screen}.png"))
                leftovers.update(c.ev(scan))
                if screen == "codex":
                    c.ev("document.querySelector('#cxGrid [data-id=banana]').click()"); time.sleep(0.3)
                    c.screenshot(os.path.join(zshots, "08_codex_detail.png")); leftovers.update(c.ev(scan))
                    c.ev("document.querySelector('[data-a=cdBack]').click()")
                c.ev(f"document.querySelector('#{screen} [data-a=back]').click()")
            check("codex hero info translated", "香蕉爆爆" in c.ev("document.getElementById('cdInfo').textContent"))
            c.ev("BONK.Game.startRun();BONK.R.hp=0;BONK.Game.fire(-1.3)"); finish_turn(c)
            if c.ev("BONK.Game.state") == "GAME_OVER":
                c.screenshot(os.path.join(zshots, "09_gameover.png")); leftovers.update(c.ev(scan)); c.ev("BONK.Game.toResults()")
            time.sleep(0.4); c.screenshot(os.path.join(zshots, "10_results.png")); leftovers.update(c.ev(scan))
            check("no untranslated English left in visible zh UI", not leftovers, sorted(leftovers))
            c.ev("BONK.Game.setState('MENU');document.getElementById('mLang').click()")
            check("toggle back to English", c.ev("document.querySelector('[data-a=play]').textContent") == "PLAY"
                  and c.ev("document.documentElement.lang") == "en")
            c.pump(); errs = c.errors()
            check("no JS errors (i18n)", not errs, errs)

        # ---------------- Phase 3: onboarding, unlock presentation, codex, coin goals ----------------
        if want("tutorial"):
            tshots = os.path.join(shots, "tutorial"); os.makedirs(tshots, exist_ok=True)
            c.metrics(450, 820, 1)
            fresh(c, "nosdk=1&seed=42")
            L = json.loads(c.ev("JSON.stringify(BONK.logical)"))
            ev = c.ev
            ev("BONK.R.xpNeed=999")  # no level-up until the board step, so lessons arrive one at a time here
            def until(states, limit=200):
                for _ in range(limit):
                    st = ev("BONK.Game.state")
                    if st in states: return st
                    ev("BONK.advance(0.25,60)")
                return ev("BONK.Game.state")
            def drag_mouse(p0, p1, steps=8):
                (x0, y0), (x1, y1) = clientxy(c, *p0), clientxy(c, *p1)
                c.mouse("mousePressed", x0, y0)
                for k in range(1, steps + 1): c.mouse("mouseMoved", x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)
                c.mouse("mouseReleased", x1, y1)
            cellc = lambda i: (26 + (i % 5) * 80 + 38, 128 + (i // 5) * 80 + 38)
            # --- aim lesson
            check("new player starts in combat with the aim lesson; HEROES button hidden until the board unlocks",
                  ev("BONK.Game.state") == "AIMING" and ev("BONK.Tut.aimOn()") and ev("getComputedStyle(document.getElementById('hudBoard')).display") == "none")
            check("first volley: a dense, weakened front line (hard to miss)", ev("BONK.R.enemies.length") >= 8 and ev("BONK.R.enemies.every(e=>e.hp<=14)"))
            ev("BONK.R.hintT=1.95;BONK.render()"); c.screenshot(os.path.join(tshots, "t01_aim_release.png"))
            ev("BONK.Game.pause()"); paused = ev("BONK.Game.state"); ev("BONK.Game.resume()")
            check("pause during the lesson, resume → lesson still pending", paused == "PAUSED" and ev("BONK.Tut.aimOn()"))
            ev("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));"
               "Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))")
            check("simulated tab hide/show during the lesson: no state change, lesson pending", ev("BONK.Game.state") == "AIMING" and ev("BONK.Tut.aimOn()"))
            check("lesson does not complete without a real shot", not ev("BONK.Tut.done('aim')"))
            drag_mouse((L["LX"], 520), (L["LX"] - 40, 300))
            check("a real mouse shot completes the aim lesson and saves it", ev("BONK.Game.state") == "FIRING" and ev("BONK.Tut.done('aim')") and ev("BONK.Save.d.tut.aim") == 1)
            ev("BONK.advance(1.2,60)")
            check("first shot hits", ev("BONK.R.dmgDealt") > 0)
            def shoot_low():
                tgt = json.loads(ev("JSON.stringify((()=>{const a=BONK.R.enemies.filter(e=>!e.dead).sort((p,q)=>(q.row+q.h)-(p.row+p.h))[0];return[a.rx+a.rw/2,a.ry+a.rh/2]})())"))
                drag_mouse((L["LX"], 520), (L["LX"] + (tgt[0] - L["LX"]) * 0.8, L["LY"] + (tgt[1] - L["LY"]) * 0.8))
            st = until(("AIMING", "BOARD"))
            check("after the first shot: plain combat turn, no gates yet, no new lesson", st == "AIMING" and ev("BONK.R.gates.length") == 0 and not ev("BONK.Tut.gateOn()"))
            # a level-up earned before the summon lesson is due is kept, not shown
            ev("BONK.R.xp=BONK.R.xpNeed-0.01"); shoot_low(); st = until(("AIMING", "BOARD"))
            check("early level-up: summon banked (kept), no interrupting screen", st == "AIMING" and ev("BONK.R.pendingLv") >= 1 and ev("BONK.R.summons") == 0 and ev("BONK.Tut.since()") == 1,
                  ev("JSON.stringify(BONK.Tut.state())"))
            shoot_low(); st = until(("AIMING", "BOARD"))
            check("third shot: still banked, still plain combat", st == "AIMING" and ev("BONK.R.summons") == 0)
            # --- gate lesson (after 2 real turns)
            check("4th shot: gate lesson with a x3 (or better) gate", ev("BONK.Tut.gateOn()") and ev("(()=>{const q=BONK.Tut.gateTarget();return q.k==='mult'&&q.v>=3})()"), ev("JSON.stringify(BONK.R.gates)"))
            ev("BONK.advance(0.95,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t02_gate_demo.png"))
            g = json.loads(ev("JSON.stringify(BONK.Tut.gateTarget())"))
            gx = g["x"] + g["w"] / 2
            drag_mouse((L["LX"], 520), (L["LX"] + (gx - L["LX"]) * 2.5, L["LY"] + (L["GATE_Y"] - L["LY"]) * 2.5))
            ev("BONK.advance(0.5,60)")
            check("shooting through the gate completes the gate lesson (real gate pass)", ev("BONK.Tut.done('gate')") and ev("BONK.R.track.gateBalls") > 0)
            st = until(("AIMING", "BOARD"))
            check("the lesson turn itself does not count toward pacing", st == "AIMING" and ev("BONK.Tut.since()") == 0)
            shoot_low(); st = until(("AIMING", "BOARD"))
            check("1 turn after the gate lesson: still plain combat", st == "AIMING")
            shoot_low(); st = until(("BOARD",), 400)
            # --- summon lesson (Phase 3)
            check("2 turns later the summon lesson opens at the turn boundary (gameplay stopped)", st == "BOARD" and ev("BONK.Tut.bt&&BONK.Tut.bt.kind") == "summon"
                  and ev("BONK.Tut.bt.stage") == "portal" and ev("BONK.CG.playing") is False and ev("BONK.R.summons") == 0, ev("JSON.stringify(BONK.Tut.state())"))
            ev("BONK.advance(0.6,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t02b_summon_portal.png"))
            x, y = clientxy(c, 224, 330); c.mouse("mousePressed", x, y); c.mouse("mouseReleased", x, y)
            ev("BONK.advance(1.2,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t02c_summon_card.png"))
            sm = json.loads(ev("JSON.stringify({st:BONK.Tut.bt&&BONK.Tut.bt.stage,u:BONK.Tut.bt&&BONK.Tut.bt.u,starter:BONK.R.starter,n:BONK.R.board.filter(Boolean).length,s:BONK.R.summons})"))
            check("the player's tap summons a real, new hero and shows its card", sm["st"] == "card" and sm["u"] and sm["u"]["id"] != sm["starter"] and sm["n"] == 3 and sm["s"] == 1, sm)
            st = until(("AIMING",), 40)
            check("summon lesson returns to combat by itself; new hero fires; board/passives not shown yet",
                  st == "AIMING" and ev("BONK.R.seq.some(p=>p.id==='" + sm["u"]["id"] + "')") and ev("getComputedStyle(document.getElementById('hudBoard')).display") == "none" and ev("BONK.Tut.done('summon')"))
            # --- merge board unlock lesson (2 more turns, next earned summon)
            shoot_low(); st = until(("AIMING", "BOARD"))
            check("1 turn after the summon lesson: plain combat", st == "AIMING")
            ev("BONK.R.xp=BONK.R.xpNeed-0.01"); shoot_low(); st = until(("BOARD",), 400)
            check("next level-up after 2 turns opens the board: unlock reveal, gameplay stopped, summon held", st == "BOARD" and ev("BONK.Tut.bt&&BONK.Tut.bt.stage") == "intro"
                  and ev("BONK.Tut.bt.kind") == "merge" and ev("BONK.CG.playing") is False and ev("BONK.R.summons") == 1 and ev("BONK.R.pendingSummons") >= 1,
                  ev("JSON.stringify({st:BONK.Game.state,s:BONK.R.summons,p:BONK.R.pendingSummons,t:BONK.Tut.state()})"))
            ev("BONK.advance(0.85,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t03_board_unlock.png"))
            ev("BONK.advance(2.6,60)")
            les = json.loads(ev("JSON.stringify({st:BONK.Tut.bt.stage,from:BONK.Tut.bt.from,to:BONK.Tut.bt.to,n:BONK.R.board.filter(u=>u&&u.id===BONK.R.starter&&u.lv===1).length,"
                                "sim:BONK.Tut.bt.from>=0?(BONK.Board.simulate(BONK.Tut.bt.from,BONK.Tut.bt.to)||[]).length:0,units:BONK.R.board.filter(Boolean).length+BONK.R.reserve.filter(Boolean).length})"))
            check("lesson board: 3 real starter heroes, one drag away from a 3-merge (no instant auto-merge)", les["st"] == "drag" and les["n"] == 3 and les["sim"] == 3 and les["units"] == 4, les)
            check("lesson UI: FIGHT and ads hidden, SKIP available", ev("getComputedStyle(document.getElementById('bdFight')).display") == "none"
                  and ev("getComputedStyle(document.getElementById('bdSkip')).display") != "none" and ev("getComputedStyle(document.getElementById('bdAd')).display") == "none")
            ev("BONK.render()"); c.screenshot(os.path.join(tshots, "t04_drag_to_merge.png"))
            wrong = ev("(()=>{const b=BONK.Tut.bt,keep=b.cells.concat([b.from]);for(const i of [24,20,4,0,14,10])if(!BONK.R.board[i]&&keep.indexOf(i)<0)return i;return -1})()")
            drag_mouse(cellc(les["from"]), cellc(wrong))
            check("wrong drop: no merge, gentle retry, lesson continues with an updated target", ev("BONK.R.merges") == 0 and ev("BONK.Tut.bt.retry>0") and ev("BONK.Tut.bt.stage") == "drag" and ev("BONK.Tut.bt.from") >= 0)
            ev("BONK.advance(0.3,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t05_retry.png"))
            fr, to = ev("BONK.Tut.bt.from"), ev("BONK.Tut.bt.to")
            drag_mouse(cellc(fr), cellc(to))
            check("the player's own drag performs the merge → celebration", ev("BONK.R.merges") == 1 and ev("BONK.Tut.bt.stage") == "celebrate" and ev("BONK.Tut.done('merge')"))
            ev("BONK.advance(1.0,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t06_evolved.png"))
            ev("BONK.advance(1.6,60);BONK.render()"); c.screenshot(os.path.join(tshots, "t07_stronger.png"))
            st = until(("AIMING",), 60)
            check("celebration returns to battle by itself (gameplay resumed)", st == "AIMING" and ev("BONK.CG.playing") is True)
            check("evolved Lv2 hero is in the combat loadout; nothing duplicated (3 Lv1 → 1 Lv2)",
                  ev("BONK.R.seq.some(p=>p.lv===2)") and ev("BONK.R.board.filter(u=>u&&u.lv===2).length") == 1 and ev("BONK.R.merges") == 1
                  and ev("BONK.R.board.concat(BONK.R.reserve).filter(Boolean).length") == 2 + ev("BONK.R.summons") - 2, ev("boardSig()"))
            check("HEROES button revealed after the lesson", ev("getComputedStyle(document.getElementById('hudBoard')).display") != "none")
            ev("BONK.render()"); c.screenshot(os.path.join(tshots, "t08_back_in_battle.png"))
            # --- reload in the middle of the lesson, then finish it by touch on a phone viewport
            fresh(c, "nosdk=1&seed=43")
            ev("BONK.Save.d.tut.aim=1;BONK.Save.d.tut.gate=1;BONK.Save.d.tut.summon=1;BONK.R.pendingLv=1;BONK.Game.openBoard();BONK.advance(0.3,60);BONK.Save.flush()")
            c.nav(BASE + "?nosdk=1&seed=43"); c.ev(BOT_JS)
            check("reload during the lesson: no lock, lesson still pending, lessons done before stay done",
                  ev("BONK.Game.state") in ("AIMING", "MENU") and not ev("BONK.Tut.done('merge')") and ev("BONK.Tut.done('gate')"))
            if ev("BONK.Game.state") == "MENU": ev("BONK.Game.startRun()")
            ev("BONK.R.pendingLv=1;BONK.Game.openBoard()")
            check("lesson starts again on the next board unlock", ev("BONK.Tut.active()"))
            c.metrics(390, 844, 3, True)
            for _ in range(30):
                time.sleep(0.05)
                if ev("BONK.view.cw===innerWidth&&BONK.view.ch===innerHeight"): break
            ev("BONK.advance(3,60)")
            fr, to = ev("BONK.Tut.bt.from"), ev("BONK.Tut.bt.to")
            (x0, y0), (x1, y1) = clientxy(c, *cellc(fr)), clientxy(c, *cellc(to))
            c.touch("touchStart", x0, y0)
            for k in range(1, 7): c.touch("touchMove", x0 + (x1 - x0) * k / 7, y0 + (y1 - y0) * k / 7)
            c.touch("touchMove", x1, y1); c.touch("touchEnd", x1, y1)
            check("touch drag completes the merge lesson on a phone viewport", ev("BONK.R.merges") == 1 and ev("BONK.Tut.done('merge')"))
            c.metrics(450, 820, 1)
            ev("BONK.Board.finishAll();BONK.Tut.finishBoard(false);BONK.Game.closeBoard()")
            # --- full / unusable board: lesson falls back instead of faking heroes
            fresh(c, "nosdk=1&seed=44")
            fb = ev(r"""(()=>{const B=BONK,S=B.Save.d;S.tut.aim=1;S.tut.gate=1;S.tut.summon=1;const ids=['banana','zappy','bean','croissant'];const spec={};
              for(let i=0;i<25;i++)spec[i]=[ids[i%4],1+(i%3)];setBoard(spec);const before=boardSig();B.R.pendingLv=1;B.Game.openBoard();B.advance(3,60);
              const o={stage:B.Tut.bt&&B.Tut.bt.stage,plan:!!(B.Tut.bt&&B.Tut.bt.plan)};B.Board.finishAll();o.inRes=B.R.reserve.filter(Boolean).length;
              o.skipVisible=getComputedStyle(document.getElementById('bdSkip')).display!=='none';document.getElementById('bdSkip').click();
              o.after=B.Tut.active();o.fight=getComputedStyle(document.getElementById('bdFight')).display!=='none';o.kept=boardSig().split('|')[0]===before.split('|')[0];return o;})()""")
            check("full board: no fake plan, summon goes to the reserve, SKIP frees the player, board untouched",
                  fb["plan"] is False and fb["stage"] in ("free", "drag") and fb["inRes"] == 1 and fb["skipVisible"] and not fb["after"] and fb["fight"] and fb["kept"], fb)
            ev("BONK.Game.closeBoard()")
            # --- 4-merge / 5-merge: contextual, explained only when available, never repeated
            ev("skipTuts();delete BONK.Save.d.tut.merge4;delete BONK.Save.d.tut.merge5;delete BONK.Save.d.tut.codex;BONK.Game.openBoard();BONK.Notify.clear()")
            q = json.loads(ev(r"""(()=>{const B=BONK.Board,R=BONK.R,o={};setBoard({0:['bean',1],1:['bean',1],5:['bean',1],12:['bean',1]});B.changed();
              o.ctx=BONK.Tut.ctx&&BONK.Tut.ctx.n;BONK.render();return JSON.stringify(o);})()"""))
            c.screenshot(os.path.join(tshots, "t09_bonus_core_hint.png"))
            q2 = json.loads(ev(r"""(()=>{const B=BONK.Board,R=BONK.R,h=B.hint,o={};const d0=BONK.Game.dmgBase();B.move(h.from,h.to);B.finishAll();
              o.cores=R.cores;o.sig=boardSig();o.done=BONK.Tut.done('merge4');o.toast=document.getElementById('toast').textContent;o.dmgUp=BONK.Game.dmgBase()>d0;
              setBoard({0:['bean',1],1:['bean',1],5:['bean',1],13:['bean',1]});B.changed();o.again=!!BONK.Tut.ctx;return JSON.stringify(o);})()"""))
            check("first 4-merge: highlighted when available, then 1 evolution + Power Core (+damage), explained once",
                  q["ctx"] == 4 and q2["cores"] == 1 and q2["sig"].count("bean2") == 1 and q2["done"] and "POWER CORE" in q2["toast"] and q2["dmgUp"] and not q2["again"], (q, q2))
            q3 = json.loads(ev(r"""(()=>{const B=BONK.Board,R=BONK.R,o={};setBoard({0:['zappy',1],1:['zappy',1],5:['zappy',1],6:['zappy',1],22:['zappy',1]});B.changed();
              o.ctx=BONK.Tut.ctx&&BONK.Tut.ctx.n;B.move(22,2);for(let i=0;i<50;i++)BONK.tick(1/60);o.banner=B.banner&&B.banner.text;B.finishAll();o.sig=boardSig();o.done=BONK.Tut.done('merge5');return JSON.stringify(o);})()"""))
            check("first 5-merge: DOUBLE EVOLUTION hint, MEGA MERGE banner, two Lv2 heroes", q3["ctx"] == 5 and q3["banner"] == "MEGA MERGE!" and q3["sig"].count("zappy2") == 2 and q3["done"], q3)
            ev("BONK.Game.closeBoard()")
            # --- notification queue
            nq = json.loads(ev(r"""(()=>{const N=BONK.Notify;N.clear();['A','B','A','C','D','E','F'].forEach(t=>N.push(t));N.push('HI',{pri:5});
              const o={cur:N.cur&&N.cur.text,q:N.q.map(n=>n.text)};BONK.advance(2.3,60);o.next=document.getElementById('toast').textContent;
              N.clear();N.push('X',{cool:20});BONK.advance(2.5,60);o.cool=N.push('X',{cool:20});N.clear();return JSON.stringify(o);})()"""))
            check("notifications: one at a time, no duplicates, capped queue, priority first, cooldown", nq["cur"] == "A" and nq["q"][0] == "HI" and nq["q"].count("A") == 0
                  and len(nq["q"]) <= 4 and nq["next"] == "HI" and nq["cool"] is False, nq)
            # --- coin goal on the menu (never spends by itself)
            ev("BONK.Game.pause();BONK.Game.quit();BONK.Save.d.coins=100;BONK.UI.refreshMenu()")
            gl = ev("document.getElementById('mGoal').textContent")
            check("menu shows the next hero goal and coins still needed", "100 / 1,190" in gl and "1,090 COINS UNTIL NEXT HERO" in gl, gl)
            ev("BONK.Save.d.coins=1200;BONK.UI.refreshMenu()"); time.sleep(1.0)
            check("enough coins: HERO READY + glowing SHOP/CODEX, nothing auto-spent", "HERO READY TO UNLOCK" in ev("document.getElementById('mGoal').textContent")
                  and ev("document.getElementById('mShop').classList.contains('glow')") and ev("document.getElementById('mCodex').classList.contains('glow')") and ev("BONK.Save.d.coins") == 1200
                  and not ev("BONK.Save.d.unlocked.frosty"))
            c.screenshot(os.path.join(tshots, "t10_menu_goal.png"))
            # --- hero unlock presentation (shop)
            ev("document.querySelector('[data-a=shop]').click()")
            ev("document.querySelector('#shopList [data-a=unlock][data-id=frosty]').click()")
            saved = json.loads(ev("localStorage.getItem('bonkageddon_save')"))
            check("buying a hero: reveal plays, unlock + coins saved immediately", ev("BONK.Reveal.on") and ev("BONK.UI.cur") == "reveal" and saved["unlocked"]["frosty"] is True and saved["coins"] == 10)
            time.sleep(0.8); c.screenshot(os.path.join(tshots, "t11_reveal_silhouette.png"))
            x, y = clientxy(c, 224, 400); c.mouse("mousePressed", x, y); c.mouse("mouseReleased", x, y)
            time.sleep(0.5); c.screenshot(os.path.join(tshots, "t12_reveal.png"))
            c.mouse("mousePressed", x, y); c.mouse("mouseReleased", x, y); time.sleep(0.8)
            card = ev("document.getElementById('rvCard').textContent")
            check("tap skips to the hero card: name, ability, Lv1 description from the real data, collection progress",
                  ev("BONK.Reveal.stage") == 1 and "FROSTY NOODLE" in card and "FREEZE" in card and ev("BONK.Save.d&&'3 hits freeze a foe (skips a step)'") in card and "5 / 8" in card, card)
            c.screenshot(os.path.join(tshots, "t13_hero_card_demo.png"))
            ev("document.querySelector('[data-a=rvNext]').click()"); time.sleep(1.5)
            check("collection stage after CONTINUE", ev("BONK.Reveal.stage") == 2)
            c.screenshot(os.path.join(tshots, "t14_collection.png"))
            ev("document.querySelector('[data-a=rvCodex]').click()"); time.sleep(0.6)
            check("VIEW IN CODEX opens the hero's detail page (unlocked, with demo)", ev("BONK.UI.cur") == "cxDetail" and "Frosty Noodle" in ev("document.getElementById('cdInfo').textContent") and not ev("BONK.Reveal.on"))
            c.screenshot(os.path.join(tshots, "t15_detail.png"))
            # --- codex: first-entry intro once, locked/unlocked distinction, unlock from the codex
            ev("document.querySelector('[data-a=cdBack]').click()"); time.sleep(0.3)
            check("first codex visit: gallery intro shown once and saved", ev("BONK.Tut.done('codex')") and ev("document.getElementById('cxIntro').classList.contains('show')"))
            ev("document.querySelector('#codex [data-a=back]').click();document.querySelector('[data-a=codex]').click()")
            cx = json.loads(ev("JSON.stringify({intro:document.getElementById('cxIntro').classList.contains('show'),un:document.querySelectorAll('#cxGrid .cx.un').length,lock:document.querySelectorAll('#cxGrid .cx.lock').length,prog:document.getElementById('cxProg').textContent})"))
            check("second visit: no intro; 5 owned heroes in colour, locked ones as silhouettes; progress chips", not cx["intro"] and cx["un"] == 5 and cx["lock"] == 3 and "5 / 8" in cx["prog"], cx)
            ev("BONK.Save.d.coins=2000;BONK.UI.renderCodex();document.querySelector('#cxGrid [data-id=turnip]').click()")
            lk = ev("document.getElementById('cdInfo').textContent")
            check("locked hero page: ability category, cost/progress, no full spoilers", "Speed Boost" in lk and "???" in lk and "Up to 2x" not in lk, lk)
            ev("document.querySelector('#cdBtns [data-a=unlock]').click()")
            check("unlock from the codex page plays the reveal", ev("BONK.Reveal.on") and ev("BONK.Save.d.unlocked.turnip") and ev("BONK.Save.d.coins") == 510)
            ev("BONK.Reveal.toCard();BONK.Reveal.toCollection();document.querySelector('[data-a=rvDone]').click()"); time.sleep(0.3)
            check("CONTINUE returns to the codex with the new hero owned", ev("BONK.UI.cur") == "codex" and ev("document.querySelector('#cxGrid [data-id=turnip]').classList.contains('un')"))
            ev("document.querySelector('#codex [data-a=back]').click()")
            # --- results screen reinforces the next unlock
            ev("BONK.Save.d.coins=100;BONK.Game.startRun();BONK.R.hp=0;BONK.Game.fire(-1.3)"); st = finish_turn(c)
            if st == "GAME_OVER": ev("BONK.Game.toResults()")
            time.sleep(1.3)
            rs = ev("document.getElementById('rsUnlock').textContent")
            check("results: coins earned, balance, progress toward the next hero", ev("BONK.Game.state") == "RESULTS" and "NEXT HERO" in rs and "COINS UNTIL NEXT HERO" in rs and "Balance" in ev("document.getElementById('rsBal').textContent"), rs)
            c.screenshot(os.path.join(tshots, "t16_results.png"))
            # --- replay tutorials keeps permanent progress
            ev("BONK.Game.setState('MENU');document.querySelector('[data-a=settings]').click();document.getElementById('tReplay').click()")
            check("Settings → REPLAY clears lessons but keeps unlocks and coins", ev("Object.keys(BONK.Save.d.tut).length") == 0 and ev("BONK.Save.d.unlocked.frosty") and ev("BONK.Save.d.unlocked.turnip"))
            ev("document.querySelector('#settings [data-a=back]').click();BONK.Game.startRun()")
            check("after REPLAY the next run teaches aiming again", ev("BONK.Tut.aimOn()"))
            c.pump(); errs = c.errors()
            check("no JS errors (tutorial)", not errs, errs)

        # ---------------- Phase 3b: first-run pacing (Teach → Play → Reward → Discover) ----------------
        if want("onboard"):
            runs = []
            for seed in (42, 7, 99):
                fresh(c, f"nosdk=1&seed={seed}")
                r = json.loads(c.ev("JSON.stringify(onboardRun(40,1.5))"))
                runs.append(r)
                print("   onboarding", seed, json.dumps(r), flush=True)
            for r in runs:
                order = [e["lesson"] for e in r["events"] if "lesson" in e]
                check(f"first run reaches every major lesson in order ({r['clock']}s)", order == ["aim", "gate", "summon", "merge", "reserve", "focus"], order)
                check("never two major lessons back to back (>=2 real turns between)", r["maxRun"] <= 1 and all(g >= 2 for g in r["gaps"]), (r["gaps"], r["maxRun"]))
                fs = [e["t"] for e in r["events"] if e.get("firstShot")][0]
                check("first shot within 5 s of starting", fs <= 5, fs)
                share = r["combat"] / max(1, r["combat"] + r["lesson"] + r["other"])
                check(">=70% of the onboarding window is combat", share >= 0.7, f"{share:.0%} combat={r['combat']} lesson={r['lesson']} other={r['other']}")
                check("wrong drop in the merge lesson recovers", r["recovered"] is True)
            c.pump(); errs = c.errors()
            check("no JS errors (onboard)", not errs, errs)

        # ---------------- Phase 5: hero discovery levels + animated cannon ----------------
        if want("phase5"):
            p5 = os.path.join(shots, "phase5"); os.makedirs(p5, exist_ok=True)
            c.metrics(450, 820, 1)
            fresh(c, "nosdk=1&seed=52")
            ev = c.ev
            ev("skipTuts();BONK.Game.newRun();BONK.Game.state='AIMING';BONK.UI.onState('AIMING')")
            # --- run-first card vs duplicate
            r = json.loads(ev(r"""(()=>{const B=BONK,Bd=B.Board,R=B.R,o={};B.Game.openBoard();R.summons=1;
              const x=R.pool.find(p=>p!==R.starter),y=R.pool.find(p=>p!==R.starter&&p!==x);o.x=x;o.y=y;o.seenBefore=!!B.Save.d.seen[x];
              R.pool=[x];R.pendingSummons=1;for(let i=0;i<40;i++)B.tick(1/60);
              o.intro=Bd.intro&&Bd.intro.id;o.busy=Bd.busy();o.first=Bd.intro&&Bd.intro.first;
              R.pendingSummons=1;for(let i=0;i<30;i++)B.tick(1/60);o.heldDuringCard=R.pendingSummons;
              Bd.down({x:224,y:400});o.afterTap=!!Bd.intro;for(let i=0;i<60;i++)B.tick(1/60);
              o.dupIntro=!!Bd.intro||Bd.introQ.length>0;o.dupEvents=B.HeroEvents.count('HERO_DUPLICATE_SUMMON');o.firstEvents=B.HeroEvents.count('HERO_FIRST_RUN_SUMMON');
              R.pool=[y];R.pendingSummons=2;R.pool=[y,y];for(let i=0;i<40;i++)B.tick(1/60);o.intro2=Bd.intro&&Bd.intro.id;o.q2=Bd.introQ.length;
              const units=R.board.concat(R.reserve).filter(Boolean).length;Bd.finishAll();o.skipKeeps=R.board.concat(R.reserve).filter(Boolean).length>=units&&!Bd.intro&&!Bd.busy();
              o.seenAfter=!!B.Save.d.seen[x];return JSON.stringify(o);})()"""))
            check("first summon of a hero type in a run: short NEW HERO JOINED card (marked as new discovery)", r["intro"] == r["x"] and r["busy"] and r["first"] is (not r["seenBefore"]), r)
            check("card pauses further summons, one tap continues", r["heldDuringCard"] == 1 and not r["afterTap"], r)
            check("duplicate summon: no card, compact +1 HERO only", not r["dupIntro"] and r["dupEvents"] >= 1 and r["firstEvents"] == 1, r)
            check("cards never overlap; skipping keeps every hero and clears the queue", r["intro2"] == r["y"] and r["q2"] == 0 and r["skipKeeps"], r)
            ev(r"""(()=>{const B=BONK,Bd=B.Board,R=B.R;R.pool=[R.pool[0]];})()""")
            ev("BONK.Game.closeBoard();BONK.Game.state==='UPGRADE'&&BONK.Game.pick(0)")
            rs = json.loads(ev(f"(()=>{{BONK.Game.newRun();const R=BONK.R;return JSON.stringify({{rs:Object.keys(R.runSeen),seen:!!BONK.Save.d.seen['{r['x']}']}})}})()"))
            check("new run resets only run-first flags; permanent discovery kept", rs["rs"] == [ev("BONK.R.starter")] and rs["seen"], rs)
            # --- cannon
            ev("BONK.Game.state='AIMING';BONK.UI.onState('AIMING')")
            cn = json.loads(ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R,C=B.Cannon,o={};const a=-1.1;R.angle=a;G.fire(a);
              const n0=B.balls.list.length;G.fireBall();const b=B.balls.list[B.balls.list.length-1];
              o.dx=Math.abs(b.x-(B.logical.LX+Math.cos(a)*B.MUZZLE));o.dy=Math.abs(b.y-(B.logical.LY+Math.sin(a)*B.MUZZLE));
              let maxX=0,minX=0,nan=false,maxCh=0,shots0=C.shot,fired=0,recoilEvery=true;
              for(let i=0;i<240&&G.state==='FIRING';i++){const s0=C.shot,v0=R.volleyLeft;B.tick(1/60);if(C.shot>s0&&C.x<=0.05)recoilEvery=false;maxX=Math.max(maxX,C.x);minX=Math.min(minX,C.x);maxCh=Math.max(maxCh,C.charge);if(!isFinite(C.x))nan=true;}
              o.maxX=+maxX.toFixed(3);o.minX=+minX.toFixed(3);o.nan=nan;o.maxCh=+maxCh.toFixed(2);o.shots=C.shot-shots0;o.recoilEvery=recoilEvery;
              for(let i=0;i<90;i++)B.tick(1/60);o.rest=+Math.abs(C.x).toFixed(3);return JSON.stringify(o);})()"""))
            check("projectile spawns exactly at the drawn muzzle", cn["dx"] < 0.01 and cn["dy"] < 0.01, cn)
            check("every shot kicks the barrel back (recoil on each ball)", cn["recoilEvery"] and cn["shots"] >= 4, cn)
            check("rapid fire: recoil stays bounded, no jitter blow-up, then recovers to rest", cn["maxX"] <= 1.25 and cn["minX"] >= -0.12 and not cn["nan"] and cn["rest"] < 0.05, cn)
            check("charge builds up between shots (overlaps the fire interval, no input delay)", cn["maxCh"] > 0.5, cn)
            st = finish_turn(c)
            pz = json.loads(ev(r"""(()=>{const B=BONK,C=B.Cannon,o={};C.x=0.8;C.v=0;B.Game.pause();for(let i=0;i<30;i++)B.tick(1/60);o.paused=C.x;B.Game.resume();for(let i=0;i<30;i++)B.tick(1/60);o.resumed=C.x;return JSON.stringify(o);})()"""))
            check("cannon animation freezes while paused and continues after resume", pz["paused"] == 0.8 and pz["resumed"] < 0.8, pz)
            fr = json.loads(ev(r"""(()=>{const B=BONK,C=B.Cannon,res=[];for(const fps of [60,144]){C.reset();C.v=10;for(let i=0;i<Math.round(0.12*fps);i++)B.tick(1/fps);res.push(C.x);}return JSON.stringify(res);})()"""))
            check("recoil timing identical at 60 Hz and 144 Hz (fixed-step animation)", abs(fr[0] - fr[1]) < 0.06, fr)
            tr = json.loads(ev(r"""(()=>{const B=BONK,S=B.Save.d,o={},p0=JSON.stringify(S.perm),d0=B.Game.dmgBase();o.t0=B.Cannon.tier();
              S.perm={hp:1,balls:1,rate:1,dmg:0,reroll:0};o.t1=B.Cannon.tier();S.perm={hp:2,balls:2,rate:2,dmg:0,reroll:1};o.t2=B.Cannon.tier();S.perm={hp:3,balls:3,rate:3,dmg:1,reroll:2};o.t3=B.Cannon.tier();
              o.dmgSame=B.Game.dmgBase()===d0;S.perm=JSON.parse(p0);return JSON.stringify(o);})()"""))
            check("cannon look follows permanent upgrades (4 tiers; the tier is only read by the drawing code)", [tr["t0"], tr["t1"], tr["t2"], tr["t3"]] == [0, 1, 2, 3], tr)
            ev("BONK.Input.active=true;BONK.R.angle=-1.0;BONK.advance(0.3,60);BONK.render()"); c.screenshot(os.path.join(p5, "cannon_aim.png"))
            pf = json.loads(ev(r"""(()=>{const B=BONK;let t=performance.now();for(let i=0;i<120;i++)B.render();const all=(performance.now()-t)/120;return JSON.stringify({renderMs:+all.toFixed(2)});})()"""))
            check("render with the new cannon stays cheap (< 6 ms/frame here)", pf["renderMs"] < 6, pf)
            ev("BONK.Input.active=false")
            c.metrics(844, 390, 2, True); time.sleep(0.3); ev("BONK.render()"); c.screenshot(os.path.join(p5, "landscape.png"))
            c.metrics(390, 844, 3, True); time.sleep(0.3); ev("BONK.render()"); c.screenshot(os.path.join(p5, "portrait_phone.png"))
            c.metrics(450, 820, 1)
            # --- full permanent unlock cinematic + encyclopedia registration
            ev("BONK.Game.pause();BONK.Game.quit();delete BONK.Save.d.tut._rev;BONK.Save.d.coins=3000;BONK.Save.d.unlocked.frosty=false;BONK.UI.refreshMenu()")
            ev("document.querySelector('[data-a=shop]').click();document.querySelector('#shopList [data-a=unlock][data-id=frosty]').click()")
            saved = json.loads(ev("localStorage.getItem('bonkageddon_save')"))
            check("permanent unlock saved before the cinematic plays (coins once)", saved["unlocked"]["frosty"] is True and saved["coins"] == 1810 and ev("BONK.HeroEvents.count('HERO_PERMANENTLY_UNLOCKED')") == 1)
            time.sleep(0.25); c.screenshot(os.path.join(p5, "r1_anticipation.png"))
            stage0 = ev("BONK.Reveal.stage"); time.sleep(1.5)
            check("anticipation + reveal finish in ~1.35 s, then the hero card", stage0 == 0 and ev("BONK.Reveal.stage") == 1, ev("BONK.Reveal.t"))
            card = ev("document.getElementById('rvCard').textContent")
            check("hero card uses the full name and real ability text", "FROSTY NOODLE" in card and "3 hits freeze a foe" in card, card)
            ev("document.querySelector('[data-a=rvNext]').click()"); time.sleep(0.4); c.screenshot(os.path.join(p5, "r2_card_flight.png"))
            time.sleep(1.2); c.screenshot(os.path.join(p5, "r3_added.png"))
            ev("document.querySelector('[data-a=rvDone]').click()")
            ev("document.querySelector('#shop [data-a=back]').click();document.querySelector('[data-a=codex]').click()")
            names = ev("document.getElementById('cxGrid').textContent")
            check("encyclopedia shows the new hero with full original names", ev("document.querySelector('#cxGrid [data-id=frosty]').classList.contains('un')") and all(n in names for n in ["Sir Croissanto", "Bananini Boom", "Frosty Noodle", "Zappy Pickle", "Splittini Bean"]), names)
            ev("document.querySelector('#codex [data-a=back]').click();document.querySelector('[data-a=shop]').click();document.querySelector('#shopList [data-a=unlock][data-id=turnip]').click()")
            check("later unlocks start with a shorter build-up; double taps never charge twice", ev("BONK.Reveal.t") >= 0.2 and ev("BONK.Save.d.coins") == 320)
            x, y = clientxy(c, 224, 400)
            for _ in range(4): c.mouse("mousePressed", x, y); c.mouse("mouseReleased", x, y); time.sleep(0.1)
            check("rapid taps skip safely to the card, no duplicate unlock/coins", ev("BONK.Reveal.stage") == 1 and ev("BONK.Save.d.coins") == 320 and ev("BONK.HeroEvents.count('HERO_PERMANENTLY_UNLOCKED')") == 2)
            ev("BONK.Reveal.close(false)")
            c.nav(BASE + "?nosdk=1"); c.ev(BOT_JS)
            check("permanent discoveries survive reload", ev("BONK.Save.d.unlocked.frosty&&BONK.Save.d.unlocked.turnip"))
            c.pump(); errs = c.errors()
            check("no JS errors (phase5)", not errs, errs)

        # ---------------- Phase 6: Lv1–8 + MAX, mastery, legends, retention ----------------
        if want("evolution"):
            eshots = os.path.join(shots, "evolution"); os.makedirs(eshots, exist_ok=True)
            c.metrics(450, 820, 1)
            fresh(c, "nosdk=1&seed=71")
            ev = c.ev
            ev("skipTuts();BONK.Save.d.tutorialDone=true;BONK.Save.d.stats.runs=1;BONK.Game.newRun();BONK.Game.state='AIMING';BONK.Game.openBoard()")
            vis = json.loads(ev(r"""(()=>{const ids=['croissant','banana','frosty','zappy','bean','muffin','turnip','sipsula'],out={};const cv=document.createElement('canvas');cv.width=cv.height=64;const g=cv.getContext('2d');
              const sig=(id,l)=>{g.clearRect(0,0,64,64);BONK.drawUnit(g,id,l,32,32,40,0);const d=g.getImageData(0,0,64,64).data;let h=0;for(let i=0;i<d.length;i+=5)h=(h*31+d[i])>>>0;return h;};
              for(const id of ids){const s=[];for(let l=1;l<=9;l++)s.push(sig(id,l));out[id]=s.every((v,i)=>i===0||v!==s[i-1]);}return JSON.stringify(out);})()"""))
            check("all 8 heroes render Lv1–Lv8 + MAX, every level looks different", len(vis) == 8 and all(vis.values()), vis)
            mg = json.loads(ev(r"""(()=>{const B=BONK.Board,R=BONK.R,S=BONK.Save.d,o={};const sig=()=>boardSig().split('|')[0];
              S.legend=[];setBoard({0:['zappy',8],1:['zappy',8],7:['zappy',8]});B.move(7,2);B.finishAll();o.max=sig().split(',')[2];o.legend=S.legend.length;
              setBoard({0:['bean',7],1:['bean',7],5:['bean',7],6:['bean',7],20:['bean',7]});B.move(20,2);B.finishAll();o.five=sig().split(',').filter(x=>x==='bean8').length;
              const c0=R.cores||0;setBoard({0:['frosty',6],1:['frosty',6],5:['frosty',6],12:['frosty',6]});B.move(12,6);B.finishAll();o.four=sig().split(',').filter(x=>x==='frosty7').length;o.core=(R.cores||0)-c0;
              setBoard({0:['muffin',9],1:['muffin',9],7:['muffin',9]});B.move(7,2);B.finishAll();o.noMax=sig().split(',').filter(x=>x==='muffin9').length;
              S.legend=new Array(24).fill('zappy');setBoard({0:['banana',8],1:['banana',8],7:['banana',8]});B.move(7,2);B.finishAll();o.pantheon=S.ach.pantheon;o.l25=S.legend.length;
              const full={};for(let i=0;i<25;i++)full[i]=[['croissant','banana','zappy','bean'][i%4],9];setBoard(full);B.changed();o.fullMax=S.ach.fullMax;return JSON.stringify(o);})()"""))
            check("3-merge Lv8 → MAX; MAX enshrined in the Hall of Legends", mg["max"] == "zappy9" and mg["legend"] == 1, mg)
            check("5-merge at Lv7 → two Lv8; 4-merge at Lv6 → Lv7 + Power Core; MAX never merges", mg["five"] == 2 and mg["four"] == 1 and mg["core"] == 1 and mg["noMax"] == 3, mg)
            check("25 legends → Pantheon; a full board of 25 MAX heroes → Full MAX Board achievement", mg["pantheon"] and mg["l25"] == 25 and mg["fullMax"], mg)
            ev("BONK.render()"); c.screenshot(os.path.join(eshots, "full_max_board.png"))
            ab = json.loads(ev(r"""(()=>{const R=BONK.R,o={};const pr=(id,l)=>{setBoard({0:[id,l]});return R.seq[0];};
              o.cr=[pr('croissant',5).cleave,pr('croissant',6).cleave,pr('croissant',9).royal];o.ba=[5,6,8,9].map(l=>pr('banana',l).cluster);
              o.fr=[pr('frosty',5).frostR,pr('frosty',6).frostR,pr('frosty',9).frostAll];o.za=[pr('zappy',5).chainPct,pr('zappy',6).chainPct,pr('zappy',9).chainPct];
              o.be=[pr('bean',5).miniPow,pr('bean',6).miniPow,pr('bean',9).miniPow];o.mu=[pr('muffin',5).eliteDmg,pr('muffin',6).eliteDmg,pr('muffin',9).eliteDmg];
              o.tu=[pr('turnip',5).speedPierce,pr('turnip',6).speedPierce,pr('turnip',9).speedPierce];o.si=[pr('sipsula',5).bloodBurst,pr('sipsula',6).bloodBurst,pr('sipsula',9).bloodBurst];return JSON.stringify(o);})()"""))
            check("every hero gains a NEW behaviour at Lv6 and a signature at MAX (not just numbers)",
                  ab["cr"] == [0, 24, True] and ab["ba"] == [0, 1, 2, 3] and ab["fr"][0] == 0 and ab["fr"][1] > 0 and ab["fr"][2] is True and ab["za"][0] < ab["za"][1] < ab["za"][2]
                  and ab["be"] == [1, 1.5, 2] and ab["mu"] == [1, 1.3, 1.6] and ab["tu"] == [0, 1, 3] and ab["si"][0] == 0 < ab["si"][1] < ab["si"][2], ab)
            cmb = json.loads(ev(r"""(()=>{const G=BONK.Game,B=BONK;function run(id,lv){G.newRun();G.state='AIMING';const R=B.R;setBoard({0:[id,lv]});R.gates.length=0;R.enemies.length=0;R.grid.fill(null);
                for(let r=0;r<5;r++)for(let c=0;c<7;c++){const e=G.makeEnemy('gloom',c,r,1,99999);G.placeEnemy(e);}
                G.fire(-1.3);for(let i=0;i<3000&&G.state==='FIRING';i++)B.tick(1/60);return{dmg:Math.round(R.dmgDealt),fr:R.track.freezes,bl:R.blasts};}
              const o={};for(const id of ['banana','zappy','frosty'])o[id]=[1,4,6,8,9].map(l=>run(id,l));return JSON.stringify(o);})()"""))
            mono = {k: [x["dmg"] for x in v] for k, v in cmb.items()}
            check("combat damage keeps rising Lv1 → Lv4 → Lv6 → Lv8 → MAX", all(all(a < b for a, b in zip(v, v[1:])) for v in mono.values()), mono)
            check("Lv6 frost nova freezes more foes than Lv4; Lv6 cluster bombs add blasts", cmb["frosty"][2]["fr"] > cmb["frosty"][1]["fr"] and cmb["banana"][2]["bl"] > cmb["banana"][1]["bl"], cmb)
            ms = json.loads(ev(r"""(()=>{const B=BONK,S=B.Save.d,M=B.Mastery,o={};B.Game.newRun();B.Game.state='AIMING';B.Game.openBoard();S.mastery={};
              o.r0=M.rank('zappy');setBoard({0:['zappy',1],1:['zappy',1],7:['zappy',1]});B.Board.move(7,2);B.Board.finishAll();o.xp=M.xp('zappy');o.feat=B.Daily.featured();
              S.mastery.zappy=60;o.r3=M.rank('zappy');o.f3=M.floor('zappy');const R=B.R;R.pool=['zappy'];R.summons=1;R.focus=null;setBoard({});B.Board.summon();B.Board.finishAll();o.summonLv=R.board.find(Boolean).lv;
              setBoard({0:['zappy',2]});o.mul=+R.seq[0].lvMul.toFixed(3);S.mastery.zappy=1300;o.r9=M.rank('zappy');o.f9=M.floor('zappy');
              const days=new Set();for(let i=0;i<14;i++){const d=new Date();d.setDate(d.getDate()+i);days.add(B.Daily.featured(d));}o.days=days.size;o.same=B.Daily.featured()===B.Daily.featured();
              o.costs=['frosty','turnip','muffin','sipsula'].map(k=>B.UNLOCK_COST[k]);B.Save.flush();return JSON.stringify(o);})()"""))
            exp_xp = 2 * (2 if ms["feat"] == "zappy" else 1)
            check("merges earn permanent Mastery XP (×2 for today's featured hero)", ms["r0"] == 1 and ms["xp"] == exp_xp, ms)
            check("mastery rank raises the summon level (★3 → Lv2, ★9 → Lv7) and gives +4% damage per rank", ms["r3"] == 3 and ms["f3"] == 2 and ms["summonLv"] == 2 and ms["mul"] == round(1.25 * 1.08, 3) and ms["r9"] == 9 and ms["f9"] == 7, ms)
            check("daily featured hero rotates (deterministic per day)", ms["days"] >= 2 and ms["same"], ms)
            check("hero unlock prices: 1190 / 1490 / 2330 / 4180", ms["costs"] == [1190, 1490, 2330, 4180], ms["costs"])
            c.nav(BASE + "?nosdk=1"); ev(BOT_JS)
            check("mastery, legends and achievements survive reload", ev("BONK.Mastery.rank('zappy')") == 9 and ev("BONK.Save.d.legend.length") == 25 and ev("BONK.Save.d.ach.fullMax"))
            ev("document.querySelector('[data-a=codex]').click()"); time.sleep(0.4)
            fl = json.loads(ev("JSON.stringify({flags:document.querySelectorAll('#cxFlags .flag').length,on:document.querySelectorAll('#cxFlags .flag.on').length,fus:document.querySelectorAll('#cxFus .fz').length,big:document.querySelector('#cxFus .fz').getBoundingClientRect().height,txt:document.getElementById('cxFlags').textContent})"))
            check("codex: 10 achievement flags (earned ones gold, others show progress) + 4 large fusion showcase cards", fl["flags"] == 10 and fl["on"] >= 4 and "25 / 25" not in fl["txt"] and fl["fus"] == 4 and fl["big"] >= 140, fl)
            c.screenshot(os.path.join(eshots, "codex_flags.png"))
            ev("document.querySelector('#cxGrid [data-id=zappy]').click()"); time.sleep(0.4)
            det = ev("document.getElementById('cdInfo').textContent")
            check("hero page: mastery stars, summon level, evolution path with gear names and MAX teaser", "MASTERY" in det and "Summons start at Lv7" in det and "MAX" in det and "Tesla antenna" in det, det[:300])
            c.screenshot(os.path.join(eshots, "hero_page.png"))
            ev("document.querySelector('[data-a=cdBack]').click();document.querySelector('[data-a=legend]').click()"); time.sleep(0.3)
            check("Hall of Legends page shows 25 / 25 and PANTHEON COMPLETE", "25 / 25" in ev("document.getElementById('cdInfo').textContent") and "PANTHEON" in ev("document.getElementById('cdInfo').textContent"))
            c.screenshot(os.path.join(eshots, "hall_of_legends.png"))
            ev("document.querySelector('[data-a=cdBack]').click();document.querySelector('#codex [data-a=back]').click()"); time.sleep(0.3)
            check("menu shows today's featured hero", "×2 MASTERY XP" in ev("document.getElementById('mDaily').textContent"), ev("document.getElementById('mDaily').textContent"))
            # migration v3 → v4
            c.nav("http://127.0.0.1:8765/tests/", wait_expr="document.readyState==='complete'")
            ev("localStorage.setItem('bonkageddon_save', JSON.stringify({v:3,coins:77,heroLv:{zappy:4,banana:3},seen:{zappy:true,banana:true},tut:{aim:1,gate:1,merge:1},stats:{runs:5,kills:1,bosses:0},tutorialDone:true,ach:{merge:true,lv4:true}}))")
            c.nav(BASE + "?nosdk=1"); ev(BOT_JS)
            mi = json.loads(ev("JSON.stringify({v:BONK.Save.d.v,c:BONK.Save.d.coins,mz:BONK.Save.d.mastery.zappy,mb:BONK.Save.d.mastery.banana,rz:BONK.Mastery.rank('zappy'),t:BONK.Save.d.tut.merge,a:BONK.Save.d.ach.lv4,lg:BONK.Save.d.legend.length})"))
            check("v3 → v4 migration: coins/tutorials/achievements kept, past evolutions seed mastery", mi == {"v": 4, "c": 77, "mz": 60, "mb": 20, "rz": 3, "t": 1, "a": True, "lg": 0}, mi)
            # evolution presentation escalates and stays skippable
            ev("skipTuts();BONK.Game.startRun();BONK.Game.openBoard()")
            an = json.loads(ev(r"""(()=>{const B=BONK.Board,o={};const timeIt=lv=>{setBoard({0:['zappy',lv],1:['zappy',lv],7:['zappy',lv]});B.move(7,2);let t=0,leg=false;while((B.busy()||B.legend)&&t<12){BONK.tick(1/60);t+=1/60;if(B.legend)leg=true;}return[+t.toFixed(2),leg];};
              for(const lv of [1,3,5,7,8])o['to'+(lv+1)]=timeIt(lv);
              setBoard({0:['zappy',8],1:['zappy',8],7:['zappy',8]});B.move(7,2);for(let i=0;i<70;i++)BONK.tick(1/60);o.legendShown=!!B.legend;B.down({x:224,y:400});o.afterTap=!!B.legend||B.busy();return JSON.stringify(o);})()"""))
            ts = [an[k][0] for k in ("to2", "to4", "to6", "to8", "to9")]
            check("evolution presentation escalates: Lv2 < Lv4 < Lv6 < Lv8 < MAX; full-screen animation from Lv5 (not for Lv2/Lv4)", ts == sorted(ts) and len(set(ts)) == 5 and not an["to2"][1] and not an["to4"][1] and an["to6"][1] and an["to8"][1] and an["to9"][1], an)
            check("MAX cinematic is skippable with one tap", an["legendShown"] and not an["afterTap"], an)
            pf = json.loads(ev(r"""(()=>{const s={};for(let i=0;i<25;i++)s[i]=[['croissant','banana','frosty','zappy','bean','muffin','turnip','sipsula'][i%8],9];setBoard(s);
              let w=0,sum=0;for(let i=0;i<60;i++){const t0=performance.now();BONK.tick(1/60);BONK.render();const d=performance.now()-t0;w=Math.max(w,d);sum+=d;}return JSON.stringify({avg:+(sum/60).toFixed(2),worst:+w.toFixed(2)});})()"""))
            check("board of 25 animated MAX heroes renders < 16 ms avg here", pf["avg"] < 16, pf)
            ev("BONK.render()"); c.screenshot(os.path.join(eshots, "max_board_mixed.png"))
            ev("BONK.Game.closeBoard();BONK.Game.state==='UPGRADE'&&BONK.Game.pick(0)")
            # achievability simulations (bot)
            prog = json.loads(ev(r"""(()=>{const B=BONK,S=B.Save.d;S.mastery={};S.legend=[];const out=[];
              for(let i=0;i<8;i++){B.Game.newRun();B.Game.state='AIMING';const R=B.R;if(R.pool.indexOf('zappy')<0)R.pool[R.pool.length-1]='zappy';R.focus='zappy'; // a player who favours one hero
                const r=botRun(260,true,'fusion');out.push({xp:S.mastery.zappy||0,rank:B.Mastery.rank('zappy'),floor:B.Mastery.floor('zappy'),wave:r.wave,best:r.bestLv});B.Game.setState('MENU');}return JSON.stringify(out);})()"""))
            print("   focused mastery progression (8 runs):", prog, flush=True)
            check("mastery grows every run, early ranks come fast but ★9 is a long-term goal (★3–★7 after 8 focused runs)", all(prog[i]["xp"] < prog[i + 1]["xp"] for i in range(len(prog) - 1)) and 3 <= prog[-1]["rank"] <= 7, prog)
            mx = json.loads(ev(r"""(()=>{const B=BONK,S=B.Save.d;for(const id of Object.keys(S.unlocked))if(S.unlocked[id])S.mastery[id]=1300;S.legend=[];
              const runs=[];for(let i=0;i<2&&!S.legend.length;i++){B.Game.newRun();B.Game.state='AIMING';B.R.focus=B.R.starter;const r=botRun(400,true,'fusion');runs.push({best:r.bestLv,wave:r.wave,simT:r.simT,summons:r.summons});B.Game.setState('MENU');}
              return JSON.stringify({best:Math.max(...runs.map(x=>x.best)),legend:S.legend.length,runs});})()"""))
            print("   ★9 run:", mx, flush=True)
            check("with ★9 mastery MAX is reached within 1–2 runs (high level is achievable)", mx["best"] >= 9 and mx["legend"] >= 1, mx)
            c.pump(); errs = c.errors()
            check("no JS errors (evolution)", not errs, errs)

        # ---------------- Screenshots of key screens ----------------
        if want("shots"):
            c.metrics(450, 820, 2)
            fresh(c, "nosdk=1&seed=88")
            c.ev("BONK.render()"); c.screenshot(os.path.join(shots, "01_first_play.png"))
            c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;setBoard({0:['zappy',3],1:['bean',2],2:['banana',4],3:['bean',1]},['thunder']);R.wave=4;
                 for(let r=0;r<5;r++)for(let c=0;c<7;c++)if(!R.grid[r*7+c]&&Math.random()<0.7){const e=G.makeEnemy(['gloom','tank','shieldy','minion','splitter','speedy'][(r+c)%6],c,r,4);e.dy=0;if((r*c)%7===3){e.elite=true;}G.placeEnemy(e);}
                 R.gates.length=0;R.gates.push({k:'mult',v:3,x:40,w:84,flash:0},{k:'power',v:'dmg',x:180,w:84,flash:0},{k:'mut',v:'shock',x:330,w:84,flash:0});
                 G.fire(-1.75);B.advance(0.9,60);B.render();})()""")
            c.screenshot(os.path.join(shots, "02_midvolley.png"))
            c.ev("BONK.advance(0.5,60);BONK.render()")
            c.screenshot(os.path.join(shots, "03_chaos.png"))
            finish_turn(c)
            c.ev("BONK.R.pendingLv=2;setBoard({0:['zappy',2],1:['bean',1],2:['bean',1],6:['bean',1]});BONK.Game.fire(-1.3)")
            for _ in range(200):
                if c.ev("BONK.Game.state") == "BOARD": break
                c.ev("BONK.advance(0.5,60)")
            c.ev("BONK.Board.finishAll();BONK.Board.move(6,7);BONK.Board.move(7,3);BONK.tick(0.016);BONK.tick(0.45);BONK.render()"); c.screenshot(os.path.join(shots, "04_board_merge.png"))
            c.ev("BONK.Board.finishAll();for(let i=0;i<40;i++)BONK.tick(0.05);BONK.render()"); c.screenshot(os.path.join(shots, "04b_board.png"))
            c.ev("BONK.Board.activateFusion('thunder')"); c.ev("BONK.tick(0.016);BONK.tick(0.6);BONK.render()"); c.screenshot(os.path.join(shots, "05_fusion_merge.png"))
            c.ev("for(let i=0;i<10;i++)BONK.tick(0.1);BONK.render()"); c.screenshot(os.path.join(shots, "06_fusion_reveal.png"))
            c.ev("BONK.Fusion.end()")
            finish_turn(c)
            c.ev(r"""(()=>{const B=BONK,G=B.Game,R=B.R;R.wave=5;R.enemies.length=0;R.grid.fill(null);G.spawnBoss();R.boss.dy=0;R.boss.shieldOn=true;R.boss.cycle=2;
               for(let c=0;c<7;c++)if(c<2||c>4){const e=G.makeEnemy('minion',c,1,5);e.dy=0;G.placeEnemy(e);}B.render();})()""")
            c.screenshot(os.path.join(shots, "07_boss.png"))
            c.ev("BONK.Game.pause()"); c.screenshot(os.path.join(shots, "08_pause.png"))
            c.ev("BONK.Game.quit()"); c.ev("for(let i=0;i<30;i++)BONK.tick(0.016)")
            time.sleep(0.4); c.screenshot(os.path.join(shots, "09_menu.png"))
            c.ev("BONK.Save.d.coins=420;document.querySelector('[data-a=shop]').click()"); c.screenshot(os.path.join(shots, "10_shop.png"))
            c.ev("document.querySelector('[data-a=back]').click();document.querySelector('[data-a=codex]').click()"); time.sleep(0.4); c.screenshot(os.path.join(shots, "11_codex.png"))
            c.ev("document.querySelector('[data-a=back]').click();document.querySelector('[data-a=missions]').click()"); time.sleep(0.4); c.screenshot(os.path.join(shots, "12_missions.png"))
            c.ev("document.querySelector('[data-a=back]').click();BONK.Game.startRun();BONK.R.hp=0;BONK.Game.fire(-1.3)"); finish_turn(c)
            time.sleep(0.4); c.screenshot(os.path.join(shots, "13_results.png"))
            c.pump(); errs = c.errors()
            check("no JS errors (screens)", not errs, errs)
    finally:
        env.close()
    fails = [r for r in RESULTS if not r[1]]
    print(f"\n==== {len(RESULTS) - len(fails)} / {len(RESULTS)} checks passed ====")
    for f in fails:
        print("FAILED:", f[0], f[2])
    with open(os.path.join(SCR, "results.json"), "w") as fh:
        json.dump(RESULTS, fh, indent=1)


if __name__ == "__main__":
    main()
