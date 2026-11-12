"""Amazon Creators API から著書の価格を取得して books/prices.json に書く。
認証情報は環境変数 AMAZON_CREATORS_ID / AMAZON_CREATORS_SECRET から読む。
新しい本を足すときは books/asins.txt に ASIN を1行足すだけ。"""
import json, os, sys, time, urllib.request, urllib.error, datetime, pathlib
HERE = pathlib.Path(__file__).resolve().parent
TAG = 'japanspiritua-22'
MP = 'www.amazon.co.jp'

def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

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
                        {'itemIds': asins[i:i + 10], 'partnerTag': TAG, 'marketplace': MP, 'condition': 'New',
                         'resources': ['offersV2.listings.price']}, h)
            if s != 429:
                break
        if s != 200:
            errors.append(f'{s}: {r}')
            continue
        for it in (r.get('itemsResult') or {}).get('items', []):
            ls = (it.get('offersV2') or {}).get('listings') or []
            best = next((l for l in ls if l.get('isBuyBoxWinner')), ls[0] if ls else None)
            m = ((best or {}).get('price') or {}).get('money')
            if m:
                prices[it['asin']] = {'amount': m['amount'], 'display': m['displayAmount']}
    if errors:
        sys.exit('一部の取得に失敗したので prices.json は書き換えない: ' + ' / '.join(errors))
    if not prices:
        sys.exit('価格が1件も取れなかった: ' + ' / '.join(errors))
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    out = {'updated': now.isoformat(), 'count': len(prices), 'prices': prices}
    (HERE / 'prices.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(prices)}/{len(asins)} 件の価格を書き出し', ('エラー: ' + ' / '.join(errors)) if errors else '')

if __name__ == '__main__':
    main()
