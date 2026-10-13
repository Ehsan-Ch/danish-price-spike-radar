"""SQLite paper cap orders. No brokerage connection or executable market quotes."""
from datetime import timedelta
import math
import sqlite3
from .data import stamp

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, area TEXT NOT NULL, issue TEXT NOT NULL, delivery TEXT NOT NULL,
 volume REAL NOT NULL, strike REAL NOT NULL, premium REAL NOT NULL, probability REAL NOT NULL,
 status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', payout REAL, settled TEXT);
CREATE TABLE IF NOT EXISTS events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL,
 time TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL);
"""

class Ledger:
    def __init__(self, path=":memory:", daily_budget=60, max_open_mwh=8, max_volume=0.5):
        if any(not math.isfinite(v) or v<=0 for v in (daily_budget,max_open_mwh,max_volume)):
            raise ValueError("Risk limits must be finite and positive")
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.daily_budget,self.max_open_mwh,self.max_volume = daily_budget,max_open_mwh,max_volume
        self.kill_switch = False

    def event(self, oid, when, status, note):
        self.db.execute("INSERT INTO events(order_id,time,status,note) VALUES(?,?,?,?)",
                        (oid,when,status,note))

    def check_clock(self, when):
        last = self.db.execute("SELECT time FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        if last and stamp(last[0]) > when:
            raise ValueError("Events must be chronological")

    def submit(self, oid, area, issue, delivery, volume, strike, premium, probability):
        issue, delivery = stamp(issue),stamp(delivery)
        if area not in ("DK1","DK2") or delivery<=issue:
            raise ValueError("Invalid area or delivery")
        if any(not math.isfinite(v) for v in (volume,strike,premium,probability)):
            raise ValueError("Nonfinite contract inputs")
        if volume<=0 or premium<0 or not 0<=probability<=1:
            raise ValueError("Invalid contract inputs")
        iso=issue.isoformat()
        self.check_clock(issue)
        if self.db.execute("SELECT 1 FROM orders WHERE area=? AND delivery=?",(area,delivery.isoformat())).fetchone():
            raise ValueError("Duplicate area/delivery contract")
        with self.db:
            self.db.execute("INSERT INTO orders(id,area,issue,delivery,volume,strike,premium,probability,status) VALUES(?,?,?,?,?,?,?,?,?)",
                (oid,area,iso,delivery.isoformat(),volume,strike,premium,probability,"SUBMITTED"))
            self.event(oid,iso,"SUBMITTED","Synthetic hourly cap request")
            spent=self.db.execute("SELECT COALESCE(SUM(volume*premium),0) FROM orders WHERE substr(issue,1,10)=? AND status IN ('OPEN','SETTLED')",(iso[:10],)).fetchone()[0]
            exposure=self.db.execute("SELECT COALESCE(SUM(volume),0) FROM orders WHERE status='OPEN'").fetchone()[0]
            reason = ("kill switch" if self.kill_switch else
                      "volume limit" if volume>self.max_volume+1e-9 else
                      "daily premium budget" if spent+volume*premium>self.daily_budget+1e-9 else
                      "open volume limit" if exposure+volume>self.max_open_mwh+1e-9 else "")
            if reason:
                self.db.execute("UPDATE orders SET status='REJECTED',reason=? WHERE id=?",(reason,oid))
                self.event(oid,iso,"REJECTED",reason)
                return "REJECTED"
            self.event(oid,iso,"APPROVED","Risk checks passed")
            self.db.execute("UPDATE orders SET status='OPEN' WHERE id=?",(oid,))
            self.event(oid,iso,"OPEN","Assumed immediate paper fill; premium paid")
            return "OPEN"

    def settle(self, oid, when, price):
        when=stamp(when)
        self.check_clock(when)
        if not math.isfinite(price):
            raise ValueError("Invalid settlement price")
        with self.db:
            order=self.db.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
            if order is None or order["status"]!="OPEN":
                raise ValueError("Only open orders can settle")
            if when<stamp(order["delivery"])+timedelta(hours=1):
                raise ValueError("Cannot settle before delivery ends")
            payout=order["volume"]*max(price-order["strike"],0)
            self.db.execute("UPDATE orders SET status='SETTLED',payout=?,settled=? WHERE id=?",
                            (payout,when.isoformat(),oid))
            self.event(oid,when.isoformat(),"SETTLED",f"Paper payout EUR {payout:.6f}")
            return payout

    def orders(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM orders ORDER BY issue,area,id")]

    def events(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY sequence")]

    def close(self):
        self.db.close()

