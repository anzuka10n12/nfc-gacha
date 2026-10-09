# 暦データ（index.html の DATA）を天文計算から作り直すスクリプト
#   使い方: pip install ephem && python3 tools/gen_data.py [終わりの日 YYYY-MM-DD]
# 1日8文字：六曜(0大安〜5仏滅) 旧暦月(2桁・閏は+20) 旧暦日(2) 日家九星(1) 節月の地支(16進1) 二十四節気(a〜x / -)
# 日家九星：冬至に最も近い甲子日から陽遁（一白から順行）、夏至に最も近い甲子日から陰遁（九紫から逆行）。
# 切替の間隔が180日にならない「閏」の時期は流派で扱いが分かれるため、その手前で止める（止めた日を表示する）。
import ephem, math, re, datetime as dt, sys, os

JST = dt.timedelta(hours=9)
START = dt.date(2025, 12, 1)
END = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2031, 11, 19)
LETTERS = 'abcdefghijklmnopqrstuvwx'

def jst_date(e): return (ephem.Date(e).datetime() + JST).date()
def sun_lon(d): return math.degrees(ephem.Ecliptic(ephem.Sun(d), epoch=d).lon)
def find_term(target, guess):
    a, b = ephem.Date(guess - 20), ephem.Date(guess + 20)
    f = lambda t: ((sun_lon(t) - target + 180) % 360) - 180
    for _ in range(60):
        m = ephem.Date((a + b) / 2)
        if f(a) * f(m) <= 0: b = m
        else: a = m
    return ephem.Date((a + b) / 2)

# 二十四節気（春分=0度）
terms = {}
for y in range(START.year - 1, END.year + 2):
    for i in range(24):
        t = find_term(i * 15, ephem.Date(dt.datetime(y, 3, 20)) + i * 365.2422 / 24)
        terms[jst_date(t)] = i

# 朔と旧暦（中気を含まない月を閏月。冬至を含む月を11月）
nm, d = [], ephem.Date(dt.datetime(START.year - 1, 10, 1))
while d < ephem.Date(dt.datetime(END.year + 1, 6, 1)):
    d = ephem.next_new_moon(d); nm.append(jst_date(d)); d = ephem.Date(d + 1)
months = [[a, b, [i for k, i in terms.items() if a <= k < b and i % 2 == 0]] for a, b in zip(nm, nm[1:])]
idx = [i for i, m in enumerate(months) if 18 in m[2]]
lab = {}
for s, e in zip(idx, idx[1:]):
    leap_done, mon = (e - s) == 12, 11
    lab[s] = (11, False)
    for j in range(s + 1, e):
        if not leap_done and not months[j][2]: lab[j] = (mon, True); leap_done = True
        else: mon = mon % 12 + 1; lab[j] = (mon, False)
def lunar(day):
    for i, (a, b, _) in enumerate(months):
        if a <= day < b and i in lab: m, leap = lab[i]; return m, leap, (day - a).days + 1
    raise ValueError(day)

def ganshi(day): return (day.toordinal() + 1721425 + 49) % 60

# 日家九星の切替点（夏至・冬至に最も近い甲子日）
def nearest_kasshi(sol):
    k = sol
    while ganshi(k) != 0: k -= dt.timedelta(days=1)
    nxt = k + dt.timedelta(days=60)
    return k if (sol - k).days <= (nxt - sol).days else nxt
switches = []
for y in range(START.year - 1, END.year + 2):
    for deg, m, yang in ((90, 6, False), (270, 12, True)):
        switches.append((nearest_kasshi(jst_date(find_term(deg, ephem.Date(dt.datetime(y, m, 21))))), yang))
switches.sort()
def star(day):
    prev = [s for s in switches if s[0] <= day][-1]
    nxt = [s for s in switches if s[0] > day][0]
    # 切替から180日目までは閏の扱いに関係なく同じ。それより先だけ止める
    if (nxt[0] - prev[0]).days != 180 and (day - prev[0]).days >= 180:
        raise SystemExit(f'{day} は閏の時期（{prev[0]}〜{nxt[0]} が{(nxt[0] - prev[0]).days}日）のため止めます')
    n = (day - prev[0]).days
    return n % 9 + 1 if prev[1] else 9 - n % 9

def setsu_branch(day):
    last = max(k for k, i in terms.items() if k <= day and i % 2 == 1)
    return ((terms[last] - 21) // 2 % 12 + 2) % 12

out, day = [], START
while day <= END:
    m, leap, ld = lunar(day)
    t = terms.get(day)
    out.append(f"{(m + ld) % 6}{m + (20 if leap else 0):02d}{ld:02d}{star(day)}{setsu_branch(day):x}{LETTERS[t] if t is not None else '-'}")
    day += dt.timedelta(days=1)
data = ''.join(out)

path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
html = open(path, encoding='utf-8').read()
old = re.search(r"const DATA = '([^']+)'", html).group(1)
n = min(len(old), len(data))
diff = [i // 8 for i in range(0, n, 8) if old[i:i + 8] != data[i:i + 8]]
print('既存データとの重なり', n // 8, '日', '不一致', len(diff), [str(START + dt.timedelta(days=i)) for i in diff[:5]])
if diff: raise SystemExit('既存データと食い違うため書き込みません')
html = html.replace(old, data, 1)
open(path, 'w', encoding='utf-8').write(html)
print('書き込み', START, '〜', END, len(data) // 8, '日')
