# 今日万年历

全自动的中文万年历静态网站,每天北京时间 00:05 由 GitHub Actions 重新生成并发布:
- 每日页:公历、农历、干支、节气、节日、星座、黄历宜忌(去年至后年,每天一页)
- 月历、年历(节日和二十四节气时间表)
- 节日倒计时(24 个传统和公历节日)、二十四节气倒计时
- 生肖年龄:1924 年至今每个出生年份属什么、今年多大,以及 12 个生肖的年份对照表
- 日期计算器:日期相差天数、日期推算、年龄计算

农历、节气、干支、宜忌由内置的 [lunar_python](https://github.com/6tail/lunar-python)(MIT 协议,见 `lunar_python/LICENSE`)离线计算,
不依赖任何外部接口,零费用。

## 一次性设置

1. 仓库设为公开;Settings → Pages → Source 选 **GitHub Actions**,Custom domain 填 `config.json` 里的域名
2. 域名 DNS:4 条 A 记录 `@` → 185.199.108.153 / 109.153 / 110.153 / 111.153,CNAME `www` → `<用户名>.github.io`

## 本地测试

```bash
python3 build.py --today 2026-10-14
python3 -m http.server -d dist
```
