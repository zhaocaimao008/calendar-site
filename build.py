#!/usr/bin/env python3
"""生成万年历静态网站到 dist/。

农历、节气、干支、宜忌等由 lunar_python(MIT,6tail)计算,全部离线完成,无需任何外部数据。
"今天"按北京时间计算,网站每天凌晨自动重新生成。

用法:
    python3 build.py                    # 以北京时间今天为准生成
    python3 build.py --today 2026-10-14 # 指定"今天"(测试用)
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

from lunar_python import Lunar, Solar

ROOT = Path(__file__).parent
OUT = ROOT / "dist"
WEEK = "一二三四五六日"

# 节日:slug, 名称, 规则, 简介
FESTIVALS = [
    ("chunjie", "春节", ("lunar", 1, 1), "农历正月初一,中国最隆重的传统节日,俗称过年。"),
    ("chuxi", "除夕", ("chuxi",), "农历年的最后一天,家人团聚吃年夜饭、守岁。"),
    ("yuanxiao", "元宵节", ("lunar", 1, 15), "农历正月十五,赏花灯、吃元宵,也是春节后的第一个月圆之夜。"),
    ("longtaitou", "龙抬头", ("lunar", 2, 2), "农历二月初二,民间有理发、吃春饼等习俗。"),
    ("qingming", "清明节", ("jieqi", "清明"), "二十四节气之一,也是扫墓祭祖的传统节日。"),
    ("duanwu", "端午节", ("lunar", 5, 5), "农历五月初五,赛龙舟、吃粽子。"),
    ("qixi", "七夕节", ("lunar", 7, 7), "农历七月初七,源自牛郎织女的传说,被称为中国情人节。"),
    ("zhongyuan", "中元节", ("lunar", 7, 15), "农历七月十五,民间有祭祖的习俗。"),
    ("zhongqiu", "中秋节", ("lunar", 8, 15), "农历八月十五,赏月、吃月饼、家人团圆。"),
    ("chongyang", "重阳节", ("lunar", 9, 9), "农历九月初九,登高、赏菊,也是敬老节。"),
    ("laba", "腊八节", ("lunar", 12, 8), "农历腊月初八,有喝腊八粥的习俗。"),
    ("xiaonian", "小年", ("lunar", 12, 23), "农历腊月二十三(北方习俗,南方多为腊月二十四),祭灶、扫尘,准备过年。"),
    ("yuandan", "元旦", ("solar", 1, 1), "公历新年的第一天。"),
    ("qingrenjie", "情人节", ("solar", 2, 14), "公历 2 月 14 日,西方情人节。"),
    ("funvjie", "妇女节", ("solar", 3, 8), "公历 3 月 8 日,国际劳动妇女节。"),
    ("zhishujie", "植树节", ("solar", 3, 12), "公历 3 月 12 日,中国植树节。"),
    ("laodongjie", "劳动节", ("solar", 5, 1), "公历 5 月 1 日,国际劳动节。"),
    ("muqinjie", "母亲节", ("nth_sunday", 5, 2), "每年 5 月的第二个星期日。"),
    ("ertongjie", "儿童节", ("solar", 6, 1), "公历 6 月 1 日,国际儿童节。"),
    ("fuqinjie", "父亲节", ("nth_sunday", 6, 3), "每年 6 月的第三个星期日。"),
    ("jiaoshijie", "教师节", ("solar", 9, 10), "公历 9 月 10 日,中国教师节。"),
    ("guoqing", "国庆节", ("solar", 10, 1), "公历 10 月 1 日,中华人民共和国国庆节。"),
    ("pinganye", "平安夜", ("solar", 12, 24), "公历 12 月 24 日,圣诞节前夜。"),
    ("shengdan", "圣诞节", ("solar", 12, 25), "公历 12 月 25 日。"),
]
JIEQI = ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
         "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒"]
JIEQI_SLUG = ["lichun", "yushui", "jingzhe", "chunfen", "qingming", "guyu", "lixia", "xiaoman", "mangzhong", "xiazhi",
              "xiaoshu", "dashu", "liqiu", "chushu", "bailu", "qiufen", "hanlu", "shuangjiang", "lidong", "xiaoxue",
              "daxue", "dongzhi", "xiaohan", "dahan"]
ANIMALS = [("shu", "鼠"), ("niu", "牛"), ("hu", "虎"), ("tu", "兔"), ("long", "龙"), ("she", "蛇"),
           ("ma", "马"), ("yang", "羊"), ("hou", "猴"), ("ji", "鸡"), ("gou", "狗"), ("zhu", "猪")]

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--text:#1d2129;--muted:#6b7280;--line:#e5e7eb;--accent:#c2410c;--soft:#fff7ed;--red:#d93025}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--text:#e6e8eb;--muted:#9aa1ac;--line:#2a2f3a;--accent:#fb923c;--soft:#2a1d14;--red:#ff7b72}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header,main,footer{max-width:860px;margin:0 auto;padding:0 16px}
header{padding-top:16px}header .logo{font-weight:700;font-size:18px;color:var(--text)}
nav{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:15px;margin-top:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin:16px 0}
h1{font-size:24px;line-height:1.4;margin:8px 0;overflow-wrap:anywhere}h2{font-size:19px;margin:0 0 12px}
.big{font-size:30px;font-weight:700;margin:4px 0}.muted{color:var(--muted);font-size:14px}.red{color:var(--red)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kv div{background:var(--bg);border-radius:8px;padding:8px 12px;font-size:13px;color:var(--muted)}.kv b{display:block;font-size:17px;color:var(--text)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left}
.cal{table-layout:fixed}.cal td,.cal th{text-align:center;padding:4px 2px;vertical-align:top}.cal td a{display:block;color:var(--text);border-radius:8px;padding:4px 0}
.cal td a:hover{background:var(--soft);text-decoration:none}.cal small{display:block;font-size:11px;color:var(--muted);line-height:1.3;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.cal .f small{color:var(--accent)}.cal .today a{background:var(--soft);outline:2px solid var(--accent)}.cal .we{color:var(--red)}
.links{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:15px}
.form{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.form label{display:flex;flex-direction:column;font-size:14px;color:var(--muted)}
.form input{font-size:17px;padding:8px 10px;margin-top:4px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);width:100%}
.out{margin-top:12px;font-size:18px;font-weight:600}.ad{margin:16px 0;min-height:90px}
footer{padding:24px 16px;color:var(--muted);font-size:13px}
"""


def esc(s):
    return html.escape(str(s))

def network_html(cfg):
    """页脚"更多实用工具":同系列网站互相链接(列表见 config.json 的 network)。"""
    sites = [s for s in cfg.get("network", []) if s["url"].rstrip("/") != cfg["base_url"].rstrip("/")]
    if not sites:
        return ""
    return "<br>更多实用工具:" + " · ".join(f'<a href="{esc(s["url"])}">{esc(s["name"])}</a>' for s in sites)



def ymd(d):
    return d.isoformat()


def cn(d):
    return f"{d.year}年{d.month}月{d.day}日"


def solar(d):
    return Solar.fromYmd(d.year, d.month, d.day)


def to_date(s):
    return dt.date(s.getYear(), s.getMonth(), s.getDay())


class Site:
    def __init__(self, today):
        self.cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.today = today
        self.y0 = today.year - self.cfg["years_before"]
        self.y1 = today.year + self.cfg["years_after"]
        self.urls = []
        # 预先算出覆盖范围内每天的农历信息
        self.days = {}
        d, end = dt.date(self.y0 - 1, 1, 1), dt.date(self.y1 + 6, 12, 31)
        while d <= end:
            self.days[d] = solar(d).getLunar()
            d += dt.timedelta(days=1)

    # ----- 计算 -----
    def occurrences(self, rule):
        """某节日在 y0-1 ~ y1+6 年的所有公历日期。"""
        kind, out = rule[0], []
        for y in range(self.y0 - 2, self.y1 + 7):
            if kind == "solar":
                out.append(dt.date(y, rule[1], rule[2]))
            elif kind == "lunar":
                out.append(to_date(Lunar.fromYmd(y, rule[1], rule[2]).getSolar()))
            elif kind == "chuxi":
                out.append(to_date(Lunar.fromYmd(y + 1, 1, 1).getSolar()) - dt.timedelta(days=1))
            elif kind == "nth_sunday":
                first = dt.date(y, rule[1], 1)
                out.append(first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (rule[2] - 1)))
            elif kind == "jieqi":
                out += [d for d, l in self.days.items() if d.year == y and l.getJieQi() == rule[1]]
        return sorted(d for d in set(out) if d in self.days)

    def next_on_or_after(self, dates):
        return next(d for d in dates if d >= self.today)

    def festivals_of(self, d):
        l = self.days[d]
        names = l.getFestivals() + l.getSolar().getFestivals()
        return list(dict.fromkeys(names))

    def countdown(self, d):
        n = (d - self.today).days
        return "就是今天" if n == 0 else (f"还有 {n} 天" if n > 0 else f"已过去 {-n} 天")

    # ----- 布局 -----
    def ad(self):
        c = self.cfg.get("adsense_client")
        if not c:
            return ""
        return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{esc(c)}" data-ad-format="auto" '
                'data-full-width-responsive="true"></ins><script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')

    def write(self, path, title, desc, body):
        cfg = self.cfg
        ads = ""
        if cfg.get("adsense_client"):
            ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
                   f'{esc(cfg["adsense_client"])}" crossorigin="anonymous"></script>')
        # 超出每日页面生成范围的日期只显示文字,不加链接
        body = re.sub(r'<a href="/d/(\d{4})-\d\d-\d\d/">(.*?)</a>',
                      lambda m: m.group(0) if self.y0 <= int(m.group(1)) <= self.y1 else m.group(2), body)
        prefix = urllib.parse.urlparse(cfg["base_url"]).path.rstrip("/")
        page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(cfg["base_url"].rstrip("/") + path)}">{ads}<style>{CSS}</style></head><body>
<header><a class="logo" href="/">{esc(cfg["site_name"])}</a><nav><a href="/">今天</a><a href="/m/{self.today:%Y-%m}/">本月日历</a>
<a href="/jieri/">节日倒计时</a><a href="/jieqi/">二十四节气</a><a href="/shengxiao/">生肖年龄</a><a href="/tools/">日期计算</a></nav></header>
<main>{body}</main>
<footer>农历、节气、干支由天文历法算法计算;黄历宜忌、冲煞等为传统民俗内容,仅供文化参考。法定节假日放假安排以国务院办公厅发布的通知为准。{network_html(cfg)}</footer>
</body></html>""".replace('href="/', f'href="{prefix}/')
        f = OUT / path.strip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page, encoding="utf-8")
        self.urls.append(path)

    # ----- 组件 -----
    def month_grid(self, y, m):
        first = dt.date(y, m, 1)
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        rows, cells = [], [""] * first.weekday()
        d = first
        while d < nxt:
            l = self.days[d]
            fest = self.festivals_of(d)
            label = l.getJieQi() or (fest[0] if fest else (f"{l.getMonthInChinese()}月" if l.getDay() == 1 else l.getDayInChinese()))
            cls = " ".join(c for c in ("f" if (fest or l.getJieQi()) else "", "today" if d == self.today else "",
                                       "we" if d.weekday() >= 5 else "") if c)
            cells.append(f'<td class="{cls}"><a href="/d/{ymd(d)}/">{d.day}<small>{esc(label)}</small></a></td>')
            d += dt.timedelta(days=1)
        cells += [""] * (-len(cells) % 7)
        for i in range(0, len(cells), 7):
            rows.append("<tr>" + "".join(c or "<td></td>" for c in cells[i:i + 7]) + "</tr>")
        head = "".join(f'<th class="{"we" if i >= 5 else ""}">{w}</th>' for i, w in enumerate(WEEK))
        return f'<table class="cal"><tr>{head}</tr>{"".join(rows)}</table>'

    def upcoming(self, n=8):
        items = []
        for slug, name, rule, _ in FESTIVALS:
            d = self.next_on_or_after(self.occurrences(rule))
            items.append((d, slug, name))
        items.sort()
        return "".join(f'<tr><td><a href="/jieri/{slug}/">{name}</a></td><td>{cn(d)} 周{WEEK[d.weekday()]}</td>'
                       f'<td>{self.countdown(d)}</td></tr>' for d, slug, name in items[:n])

    # ----- 页面 -----
    def day_page(self, d):
        l, s = self.days[d], solar(d)
        fest = self.festivals_of(d)
        jq = l.getJieQi()
        prev_jq, next_jq = l.getPrevJieQi(), l.getNextJieQi()
        yi, ji = "、".join(l.getDayYi()), "、".join(l.getDayJi())
        doy = d.timetuple().tm_yday
        days_in_year = 366 if (d.year % 4 == 0 and d.year % 100 != 0) or d.year % 400 == 0 else 365
        special = "、".join(([jq] if jq else []) + fest)
        lunar_str = f"农历{l.getMonthInChinese()}月{l.getDayInChinese()}"
        rel = (d - self.today).days
        rel_txt = "就是今天" if rel == 0 else (f"距今 {rel} 天后" if rel > 0 else f"距今 {-rel} 天前")
        pd, nd = d - dt.timedelta(days=1), d + dt.timedelta(days=1)
        nav = (f'<a href="/d/{ymd(pd)}/">« 前一天</a>' if pd.year >= self.y0 else "") + \
            f'<a href="/m/{d:%Y-%m}/">{d.year}年{d.month}月日历</a><a href="/y/{d.year}/">{d.year}年日历</a>' + \
            (f'<a href="/d/{ymd(nd)}/">后一天 »</a>' if nd.year <= self.y1 else "")
        body = f"""<div class="card"><h1>{cn(d)} 农历{l.getMonthInChinese()}月{l.getDayInChinese()} 星期{WEEK[d.weekday()]}</h1>
<div class="big">{lunar_str}</div>
<p class="muted">{l.getYearInGanZhi()}年({l.getYearShengXiao()}年) {l.getMonthInGanZhi()}月 {l.getDayInGanZhi()}日 · {rel_txt}{(' · <span class="red">' + esc(special) + '</span>') if special else ''}</p>
<div class="kv"><div>星期<b>星期{WEEK[d.weekday()]}</b></div><div>星座<b>{s.getXingZuo()}座</b></div>
<div>当年第几天<b>第 {doy} 天</b></div><div>本年剩余<b>{days_in_year - doy} 天</b></div>
<div>第几周<b>第 {d.isocalendar()[1]} 周</b></div><div>纳音<b>{l.getDayNaYin()}</b></div></div></div>
{self.ad()}
<div class="card"><h2>节气</h2><p>{f"今天是<b>{jq}</b>。" if jq else ""}上一个节气:{prev_jq.getName()}({cn(to_date(prev_jq.getSolar()))}),
下一个节气:<a href="/jieqi/{JIEQI_SLUG[JIEQI.index(next_jq.getName())]}/">{next_jq.getName()}</a>({cn(to_date(next_jq.getSolar()))})。</p></div>
<div class="card"><h2>黄历宜忌</h2><p><b>宜:</b>{esc(yi) or "—"}</p><p><b>忌:</b>{esc(ji) or "—"}</p>
<p class="muted">冲煞:冲{esc(l.getDayChongDesc())},煞{esc(l.getDaySha())} · 彭祖百忌:{esc(l.getPengZuGan())},{esc(l.getPengZuZhi())}<br>以上为传统民俗内容,仅供文化参考。</p></div>
<div class="card"><h2>本月日历</h2>{self.month_grid(d.year, d.month)}</div>
<div class="card"><div class="links">{nav}</div></div>"""
        self.write(f"/d/{ymd(d)}/",
                   f"{cn(d)}农历是多少 - {lunar_str} 星期{WEEK[d.weekday()]}{(' ' + special) if special else ''} 黄历宜忌",
                   f"{cn(d)},{lunar_str},星期{WEEK[d.weekday()]},{l.getYearInGanZhi()}年{l.getYearShengXiao()}年。{('今天是' + special + '。') if special else ''}宜{yi[:30]};忌{ji[:30]}。",
                   body)

    def month_page(self, y, m):
        fests = []
        d = dt.date(y, m, 1)
        while d.month == m:
            names = ([self.days[d].getJieQi()] if self.days[d].getJieQi() else []) + self.festivals_of(d)
            if names:
                fests.append(f'<tr><td><a href="/d/{ymd(d)}/">{m}月{d.day}日</a></td><td>{esc("、".join(names))}</td></tr>')
            d += dt.timedelta(days=1)
        pm = dt.date(y, m, 1) - dt.timedelta(days=1)
        nm = dt.date(y + (m == 12), m % 12 + 1, 1)
        nav = []
        if pm.year >= self.y0:
            nav.append(f'<a href="/m/{pm:%Y-%m}/">« {pm.year}年{pm.month}月</a>')
        nav.append(f'<a href="/y/{y}/">{y}年全年</a>')
        if nm.year <= self.y1:
            nav.append(f'<a href="/m/{nm:%Y-%m}/">{nm.year}年{nm.month}月 »</a>')
        body = f"""<div class="card"><h1>{y}年{m}月日历(含农历、节气、节日)</h1>{self.month_grid(y, m)}
<div class="links" style="margin-top:12px">{"".join(nav)}</div></div>{self.ad()}
<div class="card"><h2>{y}年{m}月节日和节气</h2><table>{"".join(fests)}</table></div>"""
        self.write(f"/m/{y}-{m:02d}/", f"{y}年{m}月日历 - {y}年{m}月农历节日节气表",
                   f"{y}年{m}月日历,带农历、二十四节气和节日,点击日期查看当天黄历宜忌。", body)

    def year_page(self, y):
        months = "".join(f'<a href="/m/{y}-{m:02d}/">{m}月</a>' for m in range(1, 13))
        jq = [(d, self.days[d].getJieQi()) for d in sorted(self.days) if d.year == y and self.days[d].getJieQi()]
        jq_rows = "".join(f'<tr><td><a href="/jieqi/{JIEQI_SLUG[JIEQI.index(n)]}/">{n}</a></td><td><a href="/d/{ymd(d)}/">{cn(d)}</a> 周{WEEK[d.weekday()]}</td></tr>' for d, n in jq)
        fr = []
        for slug, name, rule, _ in FESTIVALS:
            for d in self.occurrences(rule):
                if d.year == y:
                    fr.append((d, f'<tr><td><a href="/jieri/{slug}/">{name}</a></td><td><a href="/d/{ymd(d)}/">{cn(d)}</a> 周{WEEK[d.weekday()]}</td></tr>'))
        spring = to_date(Lunar.fromYmd(y, 1, 1).getSolar())
        animal = self.days[spring].getYearShengXiao()
        body = f"""<div class="card"><h1>{y}年日历 - {self.days[spring].getYearInGanZhi()}年({animal}年)</h1>
<p>{y}年春节是 <a href="/d/{ymd(spring)}/">{cn(spring)}</a>(星期{WEEK[spring.weekday()]}),从这一天起进入农历{self.days[spring].getYearInGanZhi()}{animal}年。</p>
<div class="links">{months}</div></div>{self.ad()}
<div class="card"><h2>{y}年节日一览</h2><table>{"".join(r for _, r in sorted(fr))}</table></div>
<div class="card"><h2>{y}年二十四节气时间表</h2><table>{jq_rows}</table></div>"""
        self.write(f"/y/{y}/", f"{y}年日历 - {y}年是什么年、春节几月几号、节日节气时间表",
                   f"{y}年是农历{self.days[spring].getYearInGanZhi()}年({animal}年),春节是{cn(spring)}。{y}年全年日历、节日和二十四节气时间表。", body)

    def festival_pages(self):
        rows = []
        for slug, name, rule, desc in FESTIVALS:
            dates = self.occurrences(rule)
            nd = self.next_on_or_after(dates)
            l = self.days[nd]
            table = "".join(f'<tr><td>{d.year}年</td><td><a href="/d/{ymd(d)}/">{d.month}月{d.day}日</a></td><td>星期{WEEK[d.weekday()]}</td>'
                            f'<td>农历{self.days[d].getMonthInChinese()}月{self.days[d].getDayInChinese()}</td></tr>'
                            for d in dates if self.today.year - 1 <= d.year <= self.today.year + 5)
            body = f"""<div class="card"><h1>距离{name}还有多少天</h1>
<div class="big">{self.countdown(nd)}</div>
<p>下一个{name}是 <a href="/d/{ymd(nd)}/">{cn(nd)}</a>,星期{WEEK[nd.weekday()]},农历{l.getMonthInChinese()}月{l.getDayInChinese()}。</p>
<p class="muted">{esc(desc)}</p></div>{self.ad()}
<div class="card"><h2>历年{name}日期</h2><table><tr><th>年份</th><th>公历</th><th>星期</th><th>农历</th></tr>{table}</table></div>
<div class="card"><h2>即将到来的节日</h2><table>{self.upcoming(8)}</table></div>"""
            self.write(f"/jieri/{slug}/", f"距离{name}还有多少天 - {nd.year}年{name}是几月几号(倒计时)",
                       f"{nd.year}年{name}是{cn(nd)},星期{WEEK[nd.weekday()]},距今{self.countdown(nd)}。附历年{name}日期表。", body)
            rows.append((nd, f'<tr><td><a href="/jieri/{slug}/">{name}</a></td><td>{cn(nd)}</td><td>{self.countdown(nd)}</td></tr>'))
        body = f'<div class="card"><h1>节日倒计时</h1><table><tr><th>节日</th><th>日期</th><th>倒计时</th></tr>{"".join(r for _, r in sorted(rows))}</table></div>'
        self.write("/jieri/", "节日倒计时 - 距离春节、中秋、国庆等节日还有多少天", "常用传统节日和公历节日倒计时,每天自动更新。", body)

    def jieqi_pages(self):
        rows = []
        for i, (name, slug) in enumerate(zip(JIEQI, JIEQI_SLUG)):
            dates = [d for d in sorted(self.days) if self.days[d].getJieQi() == name]
            nd = self.next_on_or_after(dates)
            table = "".join(f'<tr><td>{d.year}年</td><td><a href="/d/{ymd(d)}/">{d.month}月{d.day}日</a></td><td>星期{WEEK[d.weekday()]}</td></tr>'
                            for d in dates if self.today.year - 1 <= d.year <= self.today.year + 5)
            prev_n, next_n = JIEQI[i - 1], JIEQI[(i + 1) % 24]
            body = f"""<div class="card"><h1>{name}是几月几号?{nd.year}年{name}时间</h1>
<div class="big">{cn(nd)}</div><p>{self.countdown(nd)} · 星期{WEEK[nd.weekday()]} · 二十四节气第 {i + 1} 个</p>
<div class="links"><a href="/jieqi/{JIEQI_SLUG[i - 1]}/">« {prev_n}</a><a href="/jieqi/">全部节气</a><a href="/jieqi/{JIEQI_SLUG[(i + 1) % 24]}/">{next_n} »</a></div></div>{self.ad()}
<div class="card"><h2>历年{name}日期</h2><table><tr><th>年份</th><th>日期</th><th>星期</th></tr>{table}</table></div>"""
            self.write(f"/jieqi/{slug}/", f"{nd.year}年{name}是几月几号 - {name}时间及倒计时",
                       f"{nd.year}年{name}是{cn(nd)},星期{WEEK[nd.weekday()]},距今{self.countdown(nd)}。附历年{name}日期。", body)
            rows.append(f'<tr><td><a href="/jieqi/{slug}/">{name}</a></td><td>{cn(nd)}</td><td>{self.countdown(nd)}</td></tr>')
        self.write("/jieqi/", "二十四节气时间表 - 下一个节气是什么、还有几天", "二十四节气日期时间表和倒计时,每天自动更新。",
                   f'<div class="card"><h1>二十四节气</h1><table><tr><th>节气</th><th>下一次日期</th><th>倒计时</th></tr>{"".join(rows)}</table></div>')

    def shengxiao_pages(self):
        cy = self.today.year
        for y in range(self.cfg["birth_year_from"], cy + 1):
            l = Solar.fromYmd(y, 7, 1).getLunar()
            animal = l.getYearShengXiao()
            slug = next(s for s, a in ANIMALS if a == animal)
            spring = to_date(Lunar.fromYmd(y, 1, 1).getSolar())
            prev_animal = Solar.fromYmd(y, 1, 1).getLunar().getYearShengXiao()
            age = cy - y
            ben = [y + 12 * k for k in range(1, 9) if y + 12 * k <= cy + 12]
            body = f"""<div class="card"><h1>{y}年属什么生肖?{y}年出生今年多大</h1>
<div class="big">属{animal}</div>
<p>{y}年是农历{l.getYearInGanZhi()}年,{l.getYearNaYin()}命。{y}年出生的人,{cy}年<b>周岁 {age - 1 if age > 0 else 0}～{age} 岁</b>(看今年生日是否已过),<b>虚岁 {age + 1} 岁</b>。</p>
<p class="muted">注意:生肖以农历春节为界。{y}年春节是 {cn(spring)},在这天之前出生的人属{prev_animal}。</p></div>{self.ad()}
<div class="card"><h2>本命年</h2><p>属{animal}的人本命年是:{"、".join(f"{x}年" for x in ben)}。</p>
<p><a href="/shengxiao/{slug}/">查看所有属{animal}的出生年份和年龄 »</a></p></div>
<div class="card"><div class="links">{"".join(f'<a href="/shengxiao/{x}/">{x}年</a>' for x in range(max(self.cfg["birth_year_from"], y - 5), min(cy, y + 5) + 1) if x != y)}</div></div>"""
            self.write(f"/shengxiao/{y}/", f"{y}年属什么生肖 - {y}年出生今年多大({cy}年)",
                       f"{y}年是{l.getYearInGanZhi()}年,属{animal},{l.getYearNaYin()}命。{y}年出生的人{cy}年虚岁{age + 1}岁。", body)
        index = []
        for i, (slug, animal) in enumerate(ANIMALS):
            years = [y for y in range(self.cfg["birth_year_from"], cy + 13) if Solar.fromYmd(y, 7, 1).getLunar().getYearShengXiao() == animal]
            rows = "".join(f'<tr><td><a href="/shengxiao/{y}/">{y}年</a></td><td>{Solar.fromYmd(y, 7, 1).getLunar().getYearInGanZhi()}</td>'
                           f'<td>{"虚岁 " + str(cy - y + 1) + " 岁" if y <= cy else "—"}</td></tr>' for y in years if y <= cy)
            nxt = next(y for y in years if y >= cy)
            body = f"""<div class="card"><h1>属{animal}的是哪年出生的?属{animal}今年多大({cy}年)</h1>
<p>属{animal}的出生年份(按春节划分):{"、".join(f"{y}" for y in years if y <= cy)}。下一个{animal}年是 {nxt} 年{"(就是今年)" if nxt == cy else ""}。</p></div>{self.ad()}
<div class="card"><table><tr><th>出生年份</th><th>干支</th><th>{cy}年年龄</th></tr>{rows}</table></div>"""
            self.write(f"/shengxiao/{slug}/", f"属{animal}的是哪年出生的 - 属{animal}今年多大({cy}年年龄对照表)",
                       f"属{animal}的出生年份及{cy}年年龄对照表,下一个{animal}年是{nxt}年。", body)
            index.append(f'<a href="/shengxiao/{slug}/">属{animal}</a>')
        years = "".join(f'<a href="/shengxiao/{y}/">{y}</a>' for y in range(cy, self.cfg["birth_year_from"] - 1, -1))
        self.write("/shengxiao/", f"十二生肖年份对照表 - 出生年份属什么、今年多大({cy})", "十二生肖年份对照表,查询出生年份对应的生肖和今年年龄。",
                   f'<div class="card"><h1>十二生肖年龄查询</h1><div class="links">{"".join(index)}</div></div><div class="card"><h2>按出生年份查</h2><div class="links">{years}</div></div>')

    def tools_page(self):
        t = ymd(self.today)
        js = """<script>(function(){var $=function(i){return document.getElementById(i)};
function D(v){var p=v.split('-');return Date.UTC(+p[0],+p[1]-1,+p[2])}
function diff(){var a=$('a').value,b=$('b').value;if(!a||!b)return;var n=Math.round((D(b)-D(a))/864e5);
$('o1').textContent='相差 '+Math.abs(n)+' 天'+(Math.abs(n)>=7?'(约 '+Math.floor(Math.abs(n)/7)+' 周 '+Math.abs(n)%7+' 天)':'')}
function add(){var a=$('c').value,n=+$('n').value;if(!a||isNaN(n))return;var d=new Date(D(a)+n*864e5);
$('o2').textContent=d.getUTCFullYear()+'年'+(d.getUTCMonth()+1)+'月'+d.getUTCDate()+'日 星期'+'日一二三四五六'[d.getUTCDay()]}
function age(){var a=$('e').value;if(!a)return;var p=a.split('-'),t=new Date(),y=t.getFullYear()-p[0];
if(t.getMonth()+1<+p[1]||(t.getMonth()+1==+p[1]&&t.getDate()<+p[2]))y--;var days=Math.round((Date.UTC(t.getFullYear(),t.getMonth(),t.getDate())-D(a))/864e5);
$('o3').textContent='周岁 '+y+' 岁,已经度过 '+days+' 天'}
['a','b'].forEach(function(i){$(i).oninput=diff});['c','n'].forEach(function(i){$(i).oninput=add});$('e').oninput=age;diff();add();age();})();</script>"""
        body = f"""<div class="card"><h1>日期计算器</h1><p class="muted">两个日期相差多少天、某天之后 N 天是几号、年龄计算。</p></div>
<div class="card"><h2>两个日期相差多少天</h2><div class="form"><label>开始日期<input id="a" type="date" value="{t}"></label>
<label>结束日期<input id="b" type="date" value="{self.today.year + 1}-01-01"></label></div><div class="out" id="o1"></div></div>{self.ad()}
<div class="card"><h2>日期推算(N 天后/前是几号)</h2><div class="form"><label>起始日期<input id="c" type="date" value="{t}"></label>
<label>天数(负数为之前)<input id="n" type="number" value="100"></label></div><div class="out" id="o2"></div></div>
<div class="card"><h2>年龄计算</h2><div class="form"><label>出生日期<input id="e" type="date" value="1990-01-01"></label></div><div class="out" id="o3"></div></div>{js}"""
        self.write("/tools/", "日期计算器 - 两个日期相差多少天、日期推算、年龄计算", "在线日期计算器:计算两个日期相差多少天,推算 N 天后是几号,计算周岁年龄。", body)

    def home(self):
        d, l = self.today, self.days[self.today]
        nj = l.getNextJieQi()
        special = "、".join(([l.getJieQi()] if l.getJieQi() else []) + self.festivals_of(d))
        years = "".join(f'<a href="/y/{y}/">{y}年</a>' for y in range(self.y0, self.y1 + 1))
        body = f"""<div class="card"><h1>今天是{cn(d)} 星期{WEEK[d.weekday()]}</h1>
<div class="big">农历{l.getMonthInChinese()}月{l.getDayInChinese()}</div>
<p class="muted">{l.getYearInGanZhi()}年({l.getYearShengXiao()}年) {l.getMonthInGanZhi()}月 {l.getDayInGanZhi()}日{(' · <span class="red">' + esc(special) + '</span>') if special else ''}</p>
<p><b>宜:</b>{esc("、".join(l.getDayYi()[:8]))}<br><b>忌:</b>{esc("、".join(l.getDayJi()[:8]))}</p>
<p>下一个节气:<b>{nj.getName()}</b>({cn(to_date(nj.getSolar()))},{self.countdown(to_date(nj.getSolar()))}) · <a href="/d/{ymd(d)}/">今日详细黄历 »</a></p></div>{self.ad()}
<div class="card"><h2>{d.year}年{d.month}月</h2>{self.month_grid(d.year, d.month)}</div>
<div class="card"><h2>即将到来的节日</h2><table>{self.upcoming(8)}</table><p><a href="/jieri/">全部节日倒计时 »</a></p></div>
<div class="card"><h2>年历</h2><div class="links">{years}</div></div>"""
        self.write("/", f"今天农历几月几号 - {cn(d)}农历{l.getMonthInChinese()}月{l.getDayInChinese()} 万年历黄历",
                   f"今天是{cn(d)},星期{WEEK[d.weekday()]},农历{l.getMonthInChinese()}月{l.getDayInChinese()},{l.getYearInGanZhi()}年。万年历查询农历、节气、节日倒计时和黄历宜忌。", body)

    def build(self):
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir()
        self.home()
        d = dt.date(self.y0, 1, 1)
        while d <= dt.date(self.y1, 12, 31):
            self.day_page(d)
            d += dt.timedelta(days=1)
        for y in range(self.y0, self.y1 + 1):
            self.year_page(y)
            for m in range(1, 13):
                self.month_page(y, m)
        self.festival_pages()
        self.jieqi_pages()
        self.shengxiao_pages()
        self.tools_page()
        base = self.cfg["base_url"].rstrip("/")
        sm = "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{ymd(self.today)}</lastmod></url>" for u in self.urls)
        (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
        if self.cfg.get("adsense_client"):
            (OUT / "ads.txt").write_text(f"google.com, {self.cfg['adsense_client'].replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
        print(f"生成 {len(self.urls)} 个页面,今天 {ymd(self.today)}")


if __name__ == "__main__":
    if "--today" in sys.argv:
        today = dt.date.fromisoformat(sys.argv[sys.argv.index("--today") + 1])
    else:
        today = dt.datetime.now(ZoneInfo("Asia/Shanghai")).date()
    Site(today).build()
