"""Parser tests built from real messages. Run: python tools/telegram/test_extract.py"""
from extract import parse

BK_SIGNAL_EDITED = """📍 SIGNAL ID: #2183 📍
COIN: $BULLA/USDT (2-5x)
Direction: LONG
———————
Target 1: 0.0091✅
Target 2: 0.0093✅
Target 3: 0.0096✅
Target 4: 0.01✅
Target 5: 0.011✅

🔥118% Profit (5x)🔥

Our VIPs know exactly what to do to maximize profits. Book your seat now and never miss another move!
👉Message: t.me/BKConciergeBot"""

BK_UPDATE = """VIP MARKET UPDATE: $TRX
$TRX is trading around 0.3223 and drifting back down toward the long term rising trendline from the February lows, currently climbing through 0.3200 on the daily chart. Holding the trendline keeps the macro uptrend fully intact and a reclaim of 0.3300 opens the door back toward 0.3400 and higher. A daily close below 0.3200 breaks the yearly structure and exposes 0.3150 and 0.3100 below.
- Binance Killers®"""

YAGA_RESULT = "$ZRO 🔥🔥\n\nEnjoy the day 🕊"
YAGA_RESULT2 = "It was $ZRO 🔥 And I knew you would ask. 58.57% in a day"
QNT = "$QNT\n\nThe madness of whales you are watching 🔥\n\nhttps://x.com/wickprotocol/status/2104291034520396"
CLASSIC = "#SOL/USDT LONG\nEntry: 142.5 - 145\nTargets: 150, 156, 165\nStop loss: 136\nLeverage: cross 10x"
SHORT = "Short $DOGE here 0.182, SL 0.19, TP1 0.17 TP2 0.16"
AD = "🔥 GET PAID WITH BINANCE KILLERS AFFILIATE PROGRAM 🔥 Earn 20% on every sale"


def check(name, got, **want):
    for k, v in want.items():
        assert getattr(got, k) == v, f'{name}: {k}={getattr(got, k)!r}, want {v!r}'
    print('ok  ', name)


check('signal with ✅ edits stays a CALL', parse(BK_SIGNAL_EDITED, 'Binance Killers®'),
      kind='CALL', symbol='BULLA', direction='long', targets=[0.0091, 0.0093, 0.0096, 0.01, 0.011], leverage=5)
check('market update is COMMENTARY', parse(BK_UPDATE, 'Binance Killers®'), kind='COMMENTARY', symbol='TRX')
check('results channel victory lap', parse(YAGA_RESULT, 'Yaga Calls Result'), kind='RESULT', symbol='ZRO')
check('"it was $ZRO" is a RESULT', parse(YAGA_RESULT2, 'Yaga Calls Result'), kind='RESULT', symbol='ZRO')
check('hype with no levels is not a call', parse(QNT, 'Yaga Calls Result'), symbol='QNT')
assert parse(QNT, 'Yaga Calls Result').kind != 'CALL'
check('classic signal', parse(CLASSIC), kind='CALL', symbol='SOL', direction='long', entry_low=142.5,
      entry_high=145.0, targets=[150.0, 156.0, 165.0], stop=136.0, leverage=10)
check('inline short', parse(SHORT), kind='CALL', symbol='DOGE', direction='short', stop=0.19, targets=[0.17, 0.16])
check('ad is OTHER', parse(AD), kind='OTHER')
check('"target 1 hit" is a RESULT', parse('Target 1 hit on $SOL ✅ 35% profit (10x)', 'Signals A'), kind='RESULT', symbol='SOL')
check('plain "target 150"', parse('Buy $SOL entry 140, target 150, stop 130'), targets=[150.0], entry_low=140.0, stop=130.0)
check('TP1 0.17 style', parse('Short $DOGE here 0.182, SL 0.19, TP1 0.17 TP2 0.16'), targets=[0.17, 0.16])
print('all extractor tests passed')
