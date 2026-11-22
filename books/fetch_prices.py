"""Amazon Creators API から著書の価格を取得して books/prices.json に書く。
認証情報は環境変数 AMAZON_CREATORS_ID / AMAZON_CREATORS_SECRET から読む。
新しい本を足すときは books/asins.txt に ASIN を1行足すだけ。

価格の選び方:
  1. Amazon.co.jp 自身が売る新品があればその価格（Kindle 版も通常これ）
  2. 無ければ中古の最安値を「中古 ￥…」として出す（他の出品者の「新品」は使わない）
  3. 中古も無ければ、他の出品者の新品の最安値
"""
import json, os, sys, time, urllib.request, urllib.error, datetime, pathlib
HERE = pathlib.Path(__file__).resolve().parent
TAG = 'japanspiritua-22'
MP = 'www.amazon.co.jp'
AMAZON = ('Amazon.co.jp', 'Amazon Services International', 'Amazon')
RES = ['offersV2.listings.price', 'offersV2.listings.condition', 'offersV2.listings.merchantInfo']

def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

def pick(listings):
    rows = []
    for l in listings:
        m = (l.get('price') or {}).get('money')
        if not m:
            continue
        cond = ((l.get('condition') or {}).get('value') or 'New')
        merch = ((l.get('merchantInfo') or {}).get('name') or '')
        rows.append((cond, merch, m))
    amz = [m for c, n, m in rows if c == 'New' and n.startswith(AMAZON)]
    if amz:
        m = min(amz, key=lambda x: x['amount'])
        return {'amount': m['amount'], 'display': m['displayAmount']}
    used = [m for c, n, m in rows if c != 'New']
    if used:
        m = min(used, key=lambda x: x['amount'])
        return {'amount': m['amount'], 'display': '中古 ' + m['displayAmount'], 'used': True}
    new3 = [m for c, n, m in rows if c == 'New']
    if new3:
        m = min(new3, key=lambda x: x['amount'])
        return {'amount': m['amount'], 'display': m['displayAmount']}
    return None

def main():
    cid, sec = os.environ.get('AMAZON_CREATORS_ID'), os.environ.get('AMAZON_CREATORS_SECRET')
    if not cid or not sec:
        sys.exit('AMAZON_CREATORS_ID / AMAZON_CREATORS_SECRET が未設定')
    asins = [l.strip() for l in (HERE / 'asins.txt').read_text(encoding='utf-8').splitlines()
             if l.strip() and not l.startswith('#')]
    asins = list(dict.fromkeys(asins))
    s, tok = post('https://api.amazon.co.jp/auth/o2/token',
                  {'grant_type': 'client_credentials', 'client_id': cid, 'client_secret': sec,
                   'scope': 'creatorsapi::default'}, {'Content-Type': 'application/json'})
    if s != 200:
        sys.exit(f'token error {s}: {tok}')
    h = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok['access_token'],
         'x-marketplace': MP}
    prices, errors = {}, []
    for i in range(0, len(asins), 10):
        for attempt in range(5):
            if i or attempt:
                time.sleep(2 * (attempt + 1))
            s, r = post('https://creatorsapi.amazon/catalog/v1/getItems',
                        {'itemIds': asins[i:i + 10], 'partnerTag': TAG, 'marketplace': MP,
                         'condition': 'Any', 'resources': RES}, h)
            if s != 429:
                break
        if s != 200:
            errors.append(f'{s}: {r}')
            continue
        for it in (r.get('itemsResult') or {}).get('items', []):
            p = pick((it.get('offersV2') or {}).get('listings') or [])
            if p:
                prices[it['asin']] = p
    if errors:
        sys.exit('一部の取得に失敗したので prices.json は書き換えない: ' + ' / '.join(errors))
    if not prices:
        sys.exit('価格が1件も取れなかった')
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    out = {'updated': now.isoformat(), 'count': len(prices), 'prices': prices}
    (HERE / 'prices.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(prices)}/{len(asins)} 件の価格を書き出し')

if __name__ == '__main__':
    main()
