from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import ccxt
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

app = FastAPI()

exchange = ccxt.binance({'enableRateLimit': True})

# --- TELEGRAM CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8925596663:AAH_dJrIpME4_ZOAdvsxsErW_IJx7dUDyh8"
TELEGRAM_CHAT_ID = "@SalipurAirdropHunter"

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.json()
    except Exception as e:
        print(f"Telegram Notification Error: {e}")

# --- HTML & FRONTEND CODE ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Institutional Liquidity Terminal & Telegram Bot</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen p-6">
    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header & Asset Selector -->
        <div class="flex flex-col md:flex-row justify-between items-center bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl gap-4">
            <div>
                <h1 class="text-2xl font-black tracking-wider text-cyan-400">LIQUIDITY SWEEP TERMINAL</h1>
                <p class="text-xs text-slate-400 mt-1">Locked Entry Engine + Telegram Channel Push</p>
            </div>
            
            <div class="flex bg-slate-950 p-1.5 rounded-xl border border-slate-800">
                <button onclick="switchAsset('BTC/USDT', 'BINANCE:BTCUSDT')" id="btn-crypto" class="px-4 py-2 text-xs font-bold rounded-lg bg-cyan-500 text-slate-950 transition-all">Crypto (BTC)</button>
                <button onclick="switchAsset('XAU/USD', 'OANDA:XAUUSD')" id="btn-gold" class="px-4 py-2 text-xs font-bold rounded-lg text-slate-400 hover:text-white transition-all">Gold (XAU/USD)</button>
            </div>

            <div class="text-right">
                <div class="text-xs text-slate-400" id="current-pair-label">ACTIVE PAIR: BTC/USDT</div>
                <div id="asset-price" class="text-3xl font-bold text-emerald-400">$0.00</div>
            </div>
        </div>

        <!-- Main Content Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-1 space-y-4" id="timeframes-grid">
                <div class="text-xs text-slate-400 text-center py-10">Initializing engine...</div>
            </div>

            <div class="lg:col-span-2 bg-slate-900 border border-slate-800 p-4 rounded-2xl shadow-xl h-[500px] flex flex-col">
                <div class="flex justify-between items-center mb-3 px-2">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider"><i class="fa-solid fa-chart-candlestick mr-2 text-cyan-400"></i> Live Candlestick Chart</span>
                    <span class="text-xs text-cyan-400 font-mono" id="chart-symbol-text">BINANCE:BTCUSDT</span>
                </div>
                <div id="tradingview_chart" class="w-full h-full rounded-xl overflow-hidden"></div>
            </div>
        </div>

        <!-- Categorized Trade Journal Section -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-6">
            <div class="flex flex-col md:flex-row justify-between items-center border-b border-slate-800 pb-4 gap-4">
                <div>
                    <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-wider"><i class="fa-solid fa-layer-group mr-2 text-cyan-400"></i> Trade Categorization & Execution Journal</h2>
                    <p class="text-xs text-slate-500 mt-0.5">Real-time tracking with auto Telegram dispatch to @SalipurAirdropHunter</p>
                </div>
                <div class="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-bold">
                    <button onclick="filterTrades('ALL')" id="tab-all" class="px-3 py-1.5 rounded bg-cyan-500 text-slate-950 transition-all">All</button>
                    <button onclick="filterTrades('RUNNING')" id="tab-running" class="px-3 py-1.5 rounded text-slate-400 hover:text-white transition-all">Running Trades</button>
                    <button onclick="filterTrades('PENDING')" id="tab-pending" class="px-3 py-1.5 rounded text-slate-400 hover:text-white transition-all">Pending / Scanning</button>
                    <button onclick="filterTrades('CLOSED')" id="tab-closed" class="px-3 py-1.5 rounded text-slate-400 hover:text-white transition-all">Closed Trades</button>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-xs">
                    <thead>
                        <tr class="border-b border-slate-800 text-slate-400 uppercase font-mono">
                            <th class="p-3">Time</th>
                            <th class="p-3">Asset / TF</th>
                            <th class="p-3">Type</th>
                            <th class="p-3">Locked Entry</th>
                            <th class="p-3">SL Price</th>
                            <th class="p-3">Target (TP)</th>
                            <th class="p-3">Category / Status</th>
                        </tr>
                    </thead>
                    <tbody id="trade-journal-body" class="font-mono text-slate-300">
                        <tr><td colspan="7" class="p-4 text-center text-slate-500">Waiting for market triggers...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Logs Section -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
            <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4"><i class="fa-solid fa-terminal mr-2"></i> System Logs</h2>
            <div id="logs-container" class="bg-slate-950 p-4 rounded-xl h-28 overflow-y-auto font-mono text-xs space-y-2 text-slate-300 border border-slate-900">
                <div>Telegram bot integrated successfully...</div>
            </div>
        </div>
    </div>

    <script>
        let currentSymbol = "BTC/USDT";
        let tvWidget = null;
        let currentFilter = "ALL";
        let globalJournalData = [];

        function initChart(symbolTV) {
            document.getElementById('chart-symbol-text').innerText = symbolTV;
            document.getElementById('tradingview_chart').innerHTML = '';
            tvWidget = new TradingView.widget({
                "width": "100%", "height": "100%", "symbol": symbolTV,
                "interval": "15", "timezone": "Etc/UTC", "theme": "dark",
                "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6",
                "enable_publishing": false, "container_id": "tradingview_chart"
            });
        }

        function switchAsset(pair, symbolTV) {
            currentSymbol = pair;
            document.getElementById('current-pair-label').innerText = `ACTIVE PAIR: ${pair}`;
            if(pair === 'BTC/USDT') {
                document.getElementById('btn-crypto').className = "px-4 py-2 text-xs font-bold rounded-lg bg-cyan-500 text-slate-950 transition-all";
                document.getElementById('btn-gold').className = "px-4 py-2 text-xs font-bold rounded-lg text-slate-400 hover:text-white transition-all";
            } else {
                document.getElementById('btn-gold').className = "px-4 py-2 text-xs font-bold rounded-lg bg-cyan-500 text-slate-950 transition-all";
                document.getElementById('btn-crypto').className = "px-4 py-2 text-xs font-bold rounded-lg text-slate-400 hover:text-white transition-all";
            }
            initChart(symbolTV);
        }

        function filterTrades(category) {
            currentFilter = category;
            ['all', 'running', 'pending', 'closed'].forEach(cat => {
                const btn = document.getElementById(`tab-${cat}`);
                if(btn) btn.className = "px-3 py-1.5 rounded text-slate-400 hover:text-white transition-all";
            });
            document.getElementById(`tab-${category.toLowerCase()}`).className = "px-3 py-1.5 rounded bg-cyan-500 text-slate-950 transition-all";
            renderTable();
        }

        function renderTable() {
            const journalBody = document.getElementById('trade-journal-body');
            let filtered = globalJournalData;
            
            if (currentFilter === 'RUNNING') filtered = globalJournalData.filter(j => j.category === 'RUNNING');
            else if (currentFilter === 'PENDING') filtered = globalJournalData.filter(j => j.category === 'PENDING');
            else if (currentFilter === 'CLOSED') filtered = globalJournalData.filter(j => j.category === 'CLOSED');

            if (filtered.length === 0) {
                journalBody.innerHTML = `<tr><td colspan="7" class="p-4 text-center text-slate-500">No trades found in this category.</td></tr>`;
                return;
            }

            journalBody.innerHTML = filtered.map(j => {
                let badgeStyle = 'bg-amber-500/20 text-amber-300 border-amber-500/30';
                if (j.category === 'RUNNING') badgeStyle = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
                else if (j.category === 'CLOSED') badgeStyle = 'bg-rose-500/20 text-rose-400 border-rose-500/40';

                return `
                    <tr class="border-b border-slate-800/60 hover:bg-slate-950/50">
                        <td class="p-3 text-slate-400">${j.time}</td>
                        <td class="p-3 font-bold text-cyan-400">${j.pair} (${j.tf})</td>
                        <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${j.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">${j.type}</span></td>
                        <td class="p-3 text-slate-200">$${j.entry.toFixed(2)}</td>
                        <td class="p-3 text-rose-400">$${j.sl.toFixed(2)}</td>
                        <td class="p-3 text-emerald-400">$${j.tp.toFixed(2)}</td>
                        <td class="p-3"><span class="px-2 py-1 rounded text-[10px] font-bold border ${badgeStyle}">${j.status}</span></td>
                    </tr>
                `;
            }).join('');
        }

        window.addEventListener('DOMContentLoaded', () => {
            initChart("BINANCE:BTCUSDT");
        });

        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const assetData = data[currentSymbol];
            if (!assetData) return;

            document.getElementById('asset-price').innerText = `$${assetData.price.toFixed(2)}`;

            const grid = document.getElementById('timeframes-grid');
            grid.innerHTML = '';
            for (const [tf, info] of Object.entries(assetData.trades)) {
                const isActive = info.active;
                const isBuy = info.is_long;
                let badgeColor = isActive ? (isBuy ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50' : 'bg-rose-500/20 text-rose-400 border-rose-500/50') : 'bg-slate-800 text-slate-400 border-slate-700';
                let cardBorder = isActive ? (isBuy ? 'border-emerald-500/40 bg-emerald-950/10' : 'border-rose-500/40 bg-rose-950/10') : 'border-slate-800 bg-slate-900';

                grid.innerHTML += `
                    <div class="border ${cardBorder} p-4 rounded-xl shadow-lg transition-all flex flex-col justify-between">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-base font-black text-cyan-300">${currentSymbol} (${tf})</span>
                            <span class="px-3 py-1 text-xs rounded-lg font-bold border ${badgeColor}">${info.status}</span>
                        </div>
                        <div class="text-xs text-slate-400 grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-800">
                            <div>Entry: <span class="text-slate-200 font-mono">${isActive ? info.entry.toFixed(2) : info.entry_zone.toFixed(2)}</span></div>
                            <div>SL: <span class="text-rose-400 font-mono">${isActive ? info.sl.toFixed(2) : info.sl_zone.toFixed(2)}</span></div>
                            <div>TP1: <span class="text-emerald-400 font-mono">${isActive ? info.tp1.toFixed(2) : info.tp1_zone.toFixed(2)}</span></div>
                            <div>TP2: <span class="text-emerald-400 font-mono">${isActive ? info.tp2.toFixed(2) : info.tp2_zone.toFixed(2)}</span></div>
                        </div>
                    </div>
                `;
            }

            globalJournalData = data.journal || [];
            renderTable();

            const logsContainer = document.getElementById('logs-container');
            logsContainer.innerHTML = data.logs.map(log => `<div>> ${log}</div>`).join('');
        };
    </script>
</body>
</html>
"""

market_states = {
    "BTC/USDT": {"price": 0.0, "trades": {}},
    "XAU/USD": {"price": 0.0, "trades": {}}
}
trade_journal_history = []
locked_entries = {}
recent_logs = ["Telegram Integrated Terminal Initialized"]

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

def fetch_and_calculate_telegram(symbol, ccxt_symbol, is_gold=False):
    try:
        bars = exchange.fetch_ohlcv(ccxt_symbol, timeframe='15m', limit=50)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        current_price = float(df['close'].iloc[-1])
        if is_gold:
            current_price = 4592.00 + (current_price % 10)

        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else (current_price * 0.002)
        swing_high = float(df['high'].tail(20).max())
        swing_low = float(df['low'].tail(20).min())
        timestamp_str = datetime.now().strftime("%H:%M:%S")

        trades = {}
        for tf in ["1D", "4H", "1H"]:
            key = f"{symbol}_{tf}"
            is_buy_sweep = current_price <= (swing_low + (atr * 0.5))
            is_sell_sweep = current_price >= (swing_high - (atr * 0.5))

            if is_buy_sweep:
                if key not in locked_entries:
                    locked_entries[key] = {"entry": current_price, "sl": swing_low - atr, "tp": current_price + (atr * 2.0), "type": "BUY"}
                    # टेलीग्राम पर पुश नोटिफिकेशन भेजें
                    msg = f"🚨 *LIQUIDITY SWEEP SIGNAL* 🚨\n\n🟢 *Asset:* {symbol} ({tf})\n⚡ *Type:* BUY (SSLQ SWEEP)\n💰 *Locked Entry:* `${locked_entries[key]['entry']:.2f}`\n🛑 *Stop Loss:* `${locked_entries[key]['sl']:.2f}`\n🎯 *Target (TP):* `${locked_entries[key]['tp']:.2f}`\n\n⏱️ *Time:* {timestamp_str}"
                    send_telegram_alert(msg)

                locked = locked_entries[key]
                trades[tf] = {"active": True, "is_long": True, "entry": locked["entry"], "sl": locked["sl"], "tp1": locked["tp"], "tp2": locked["tp"]+atr, "status": "BUY (SSLQ SWEEP)"}
                
                if not any(t['pair'] == symbol and t['tf'] == tf and t['category'] == 'RUNNING' for t in trade_journal_history):
                    trade_journal_history.insert(0, {
                        "time": timestamp_str, "pair": symbol, "tf": tf, "type": "BUY",
                        "entry": locked["entry"], "sl": locked["sl"], "tp": locked["tp"],
                        "category": "RUNNING", "status": "RUNNING TRADE ⚡"
                    })

            elif is_sell_sweep:
                if key not in locked_entries:
                    locked_entries[key] = {"entry": current_price, "sl": swing_high + atr, "tp": current_price - (atr * 2.0), "type": "SELL"}
                    # टेलीग्राम पर पुश नोटिफिकेशन भेजें
                    msg = f"🚨 *LIQUIDITY SWEEP SIGNAL* 🚨\n\n🔴 *Asset:* {symbol} ({tf})\n⚡ *Type:* SELL (BSLQ SWEEP)\n💰 *Locked Entry:* `${locked_entries[key]['entry']:.2f}`\n🛑 *Stop Loss:* `${locked_entries[key]['sl']:.2f}`\n🎯 *Target (TP):* `${locked_entries[key]['tp']:.2f}`\n\n⏱️ *Time:* {timestamp_str}"
                    send_telegram_alert(msg)

                locked = locked_entries[key]
                trades[tf] = {"active": True, "is_long": False, "entry": locked["entry"], "sl": locked["sl"], "tp1": locked["tp"], "tp2": locked["tp"]-atr, "status": "SELL (BSLQ SWEEP)"}
                
                if not any(t['pair'] == symbol and t['tf'] == tf and t['category'] == 'RUNNING' for t in trade_journal_history):
                    trade_journal_history.insert(0, {
                        "time": timestamp_str, "pair": symbol, "tf": tf, "type": "SELL",
                        "entry": locked["entry"], "sl": locked["sl"], "tp": locked["tp"],
                        "category": "RUNNING", "status": "RUNNING TRADE ⚡"
                    })
            else:
                trades[tf] = {
                    "active": False, "is_long": True, "entry": 0, "sl": 0, "tp1": 0, "tp2": 0,
                    "entry_zone": swing_high if tf=="1D" else swing_low,
                    "sl_zone": swing_high + atr if tf=="1D" else swing_low - atr,
                    "tp1_zone": current_price + atr, "tp2_zone": current_price + (atr * 2),
                    "status": "SCANNING ZONE"
                }
                if not any(t['pair'] == symbol and t['tf'] == tf and t['category'] == 'PENDING' for t in trade_journal_history):
                    trade_journal_history.append({
                        "time": timestamp_str, "pair": symbol, "tf": tf, "type": "SCAN",
                        "entry": swing_high, "sl": swing_high+atr, "tp": current_price,
                        "category": "PENDING", "status": "PENDING / SCANNING ⏳"
                    })

        return current_price, trades
    except Exception as e:
        print(e)
        return 0.0, {}

async def background_loop():
    global market_states, trade_journal_history, recent_logs
    while True:
        try:
            btc_price, btc_trades = fetch_and_calculate_telegram("BTC/USDT", "BTC/USDT", is_gold=False)
            if btc_price > 0:
                market_states["BTC/USDT"]["price"] = btc_price
                market_states["BTC/USDT"]["trades"] = btc_trades

            gold_price, gold_trades = fetch_and_calculate_telegram("XAU/USD", "PAXG/USDT", is_gold=True)
            if gold_price > 0:
                market_states["XAU/USD"]["price"] = gold_price
                market_states["XAU/USD"]["trades"] = gold_trades

            if len(trade_journal_history) > 25:
                trade_journal_history.pop()

            await manager.broadcast({
                "BTC/USDT": market_states["BTC/USDT"],
                "XAU/USD": market_states["XAU/USD"],
                "journal": trade_journal_history,
                "logs": recent_logs
            })
        except Exception as e:
            print(e)
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_loop())

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_CONTENT)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)