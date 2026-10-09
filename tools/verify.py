# 暦データの検証スクリプト
# index.html の DATA（旧暦・六曜・日家九星・節月・二十四節気）と SETSU（節入り日）を、
# 天文計算ライブラリ ephem で独立に計算し直して照合する。
#   使い方: pip install ephem && python3 tools/verify.py
import ephem, math, re, datetime as dt, sys, os
html = open(os.path.join(os.path.dirname(__file__), '..', 'index.html'), encoding='utf-8').read()
DATA = re.search(r"const DATA = '([^']+)'", html).group(1)
START = dt.date(2025,12,1)
JST = dt.timedelta(hours=9)

def jst_date(edate):  # ephem.Date(UTC) -> JSTの日付
    return (ephem.Date(edate).datetime() + JST).date()

def sun_lon(d):
    s = ephem.Sun(d); return math.degrees(ephem.Ecliptic(s, epoch=d).lon)  # 視黄経(その日の分点)

def find_term(target, guess):
    # 太陽黄経が target 度になる時刻（二分法）
    a, b = ephem.Date(guess - 20), ephem.Date(guess + 20)
    f = lambda t: ((sun_lon(t) - target + 180) % 360) - 180
    for _ in range(60):
        m = ephem.Date((a + b) / 2)
        if f(a) * f(m) <= 0: b = m
        else: a = m
    return ephem.Date((a + b) / 2)

# 二十四節気（春分=0度 から15度刻み）
terms = {}
names = ['春分','清明','穀雨','立夏','小満','芒種','夏至','小暑','大暑','立秋','処暑','白露','秋分','寒露','霜降','立冬','小雪','大雪','冬至','小寒','大寒','立春','雨水','啓蟄']
for y in range(2024, 2034):
    for i in range(24):
        deg = i * 15
        # おおよその日付: 春分≒3/20
        guess = ephem.Date(dt.datetime(y,3,20)) + i * 365.2422 / 24
        t = find_term(deg, guess)
        terms[jst_date(t)] = (i, names[i], t)

# 朔（新月）
nm = []
d = ephem.Date(dt.datetime(2024,10,1))
while d < ephem.Date(dt.datetime(2033,3,1)):
    d = ephem.next_new_moon(d); nm.append(jst_date(d)); d = ephem.Date(d + 1)

# 旧暦（天保暦の規則：中気を含まない月を閏月。冬至を含む月を11月）
months = []  # (開始日, 次の開始日, 中気リスト)
for a, b in zip(nm, nm[1:]):
    zq = [v[0] for k, v in terms.items() if a <= k < b and v[0] % 2 == 0]
    months.append([a, b, zq])
# 冬至(18)を含む月を11月とし、次の冬至月まで番号付け
def label():
    idx = [i for i, m in enumerate(months) if 18 in m[2]]
    lab = {}
    for s, e in zip(idx, idx[1:]):
        n = e - s  # 12 or 13
        leap_done = n == 12
        mon = 11
        lab[s] = (11, False)
        for j in range(s + 1, e):
            if not leap_done and not months[j][2]:
                lab[j] = (mon, True); leap_done = True
            else:
                mon = mon % 12 + 1; lab[j] = (mon, False)
    return lab
lab = label()
def lunar(day):
    for i, (a, b, _) in enumerate(months):
        if a <= day < b and i in lab:
            m, leap = lab[i]; return m, leap, (day - a).days + 1
    return None

def ganshi(day):
    jdn = day.toordinal() + 1721425
    return (jdn + 49) % 60

ROK = ['大安','赤口','先勝','友引','先負','仏滅']
LETTERS = 'abcdefghijklmnopqrstuvwx'
errs = {'rokuyo':0,'lunar':0,'term':0,'sb':0}
samples = []
n = len(DATA)//8
stars = []
for i in range(n):
    day = START + dt.timedelta(days=i)
    r = DATA[i*8:i*8+8]
    rok, lmr, ld, star, sb, tch = int(r[0]), int(r[1:3]), int(r[3:5]), int(r[5]), int(r[6],16), r[7]
    lm, leap = (lmr-20, True) if lmr > 20 else (lmr, False)
    L = lunar(day)
    if L != (lm, leap, ld):
        errs['lunar'] += 1; samples.append((day, 'lunar', (lm,leap,ld), L))
    exp_rok = (L[0] + L[2]) % 6
    if rok != exp_rok:
        errs['rokuyo'] += 1; samples.append((day,'rokuyo',ROK[rok],ROK[exp_rok]))
    t = terms.get(day)
    exp_t = LETTERS[t[0]] if t else '-'
    if tch != exp_t:
        errs['term'] += 1; samples.append((day,'term',tch,exp_t))
    stars.append((day, star, ganshi(day)))
    # 節月の地支: 直前の「節」(奇数index)から求める。立春(21)=寅(2)
    last = max(k for k,v in terms.items() if k <= day and v[0] % 2 == 1)
    ti = terms[last][0]
    exp_sb = ((ti - 21) // 2 % 12 + 2) % 12
    if sb != exp_sb:
        errs['sb'] += 1; samples.append((day,'sb',sb,exp_sb))

print('日数', n, START, '〜', START + dt.timedelta(days=n-1))
print('不一致', errs)
for s in samples[:20]: print(s)

# 日家九星：遁の切替点と、その日の干支・値
print('--- 日家九星の切替点（遁の向きが変わる日） ---')
prevstep = None
for (d0,s0,g0),(d1,s1,g1) in zip(stars, stars[1:]):
    step = (s1 - s0) % 9
    if step not in (1,8):
        print('遁の切替（同じ星が2日続く）', d0, s0, s1)
        # 切替の日（2日目）は甲子日で、陽遁は一白・陰遁は九紫から始まるはず
        if not (step == 0 and g1 == 0 and s1 in (1, 9)): errs['kyusei'] = errs.get('kyusei', 0) + 1; print('  ↑切替の規則と合いません')
    if prevstep is not None and step != prevstep:
        print(d1, '星', s1, '干支番号', g1, '(甲子=0/甲午=30)', '陽遁' if step==1 else '陰遁')
    prevstep = step
# 冬至・夏至の日付
for k,v in sorted(terms.items()):
    if v[1] in ('冬至','夏至') and START <= k <= START + dt.timedelta(days=n): print(v[1], k)

# --- 節入り日表（SETSU）の照合 ---
# 1900〜2100年の「節入り日」（各月の節：小寒〜大雪）をJSTで計算し、1年12桁の文字列にする
def lon(d): return math.degrees(ephem.Ecliptic(ephem.Sun(d), epoch=d).lon)
def find(target, guess):
    a, b = ephem.Date(guess - 15), ephem.Date(guess + 15)
    f = lambda t: ((lon(t) - target + 180) % 360) - 180
    for _ in range(50):
        m = ephem.Date((a + b) / 2)
        if f(a) * f(m) <= 0: b = m
        else: a = m
    return (ephem.Date((a+b)/2).datetime() + JST).date()
DEG = [285,315,345,15,45,75,105,135,165,195,225,255]   # 1月〜12月の節
out = []
for y in range(1900, 2101):
    for m, deg in enumerate(DEG, 1):
        d = find(deg, ephem.Date(dt.datetime(y, m, 6)))
        assert d.year == y and d.month == m and 1 <= d.day <= 9, (y, m, d)
        out.append(str(d.day))
s = ''.join(out)
embedded = re.search(r"const SETSU = '(\d+)'", html).group(1)
diff = [(1900 + i // 12, i % 12 + 1) for i, (p, q) in enumerate(zip(s, embedded)) if p != q]
print('節入り日表', len(embedded), '桁', '不一致', len(diff), diff[:10])
print('日家九星の切替', '不一致', errs.get('kyusei', 0))
ok = not any(errs.values()) and not diff and len(s) == len(embedded)
print('結果:', 'すべて一致' if ok else '不一致あり')
sys.exit(0 if ok else 1)
