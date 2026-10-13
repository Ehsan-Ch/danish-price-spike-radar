import json
import math
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
import numpy as np
from spikeradar.data import normalize, stamp, load
from spikeradar.model import features, Logistic, auc, metrics
from spikeradar.ledger import Ledger
from spikeradar.pipeline import simulate, tail_summary, rolling_probability, fit_area
from spikeradar.report import render

class DataTests(unittest.TestCase):
    def rows(self):
        return [{"TimeUTC":f"2026-01-01T00:{m:02d}:00","PriceArea":"DK1","DayAheadPriceEUR":v}
                for m,v in zip((0,15,30,45),(-40,0,40,80))]
    def test_hour_average_and_negative_prices(self):
        series,q=normalize({"records":self.rows()})
        self.assertEqual(series["DK1"][stamp("2026-01-01")],20)
        self.assertEqual(q["incomplete_hours"],0)
    def test_missing_quarter_not_imputed(self):
        series,q=normalize({"records":self.rows()[:3]})
        self.assertEqual(series["DK1"],{})
        self.assertEqual(q["incomplete_hours"],1)
    def test_invalid_quarter_discards_hour(self):
        rows=self.rows();rows[0]["DayAheadPriceEUR"]=None
        series,q=normalize({"records":rows})
        self.assertEqual(series["DK1"],{})
        self.assertEqual(q["invalid_quarters"],1)
    def test_duplicate_rejected(self):
        rows=self.rows()
        with self.assertRaises(ValueError):
            normalize({"records":rows+[rows[0]]})
    def test_bad_alignment_rejected(self):
        rows=self.rows();rows[0]["TimeUTC"]="2026-01-01T00:01:00"
        with self.assertRaises(ValueError):
            normalize({"records":rows})
    def test_utc_offsets_do_not_collapse_dst_hours(self):
        self.assertEqual(stamp("2026-10-25T02:00:00+02:00"),stamp("2026-10-25T00:00:00Z"))
        self.assertNotEqual(stamp("2026-10-25T02:00:00+02:00"),stamp("2026-10-25T02:00:00+01:00"))
    def test_cache_tampering_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"prices.json").write_text("{}")
            (p/"manifest.json").write_text(json.dumps({"sha256":"bad"}))
            with self.assertRaises(ValueError):
                load(p)

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.target=stamp("2026-07-02")
        self.series={self.target-timedelta(hours=h):100+20*math.sin(h/24) for h in range(400)}
    def test_no_feature_after_information_cutoff(self):
        before=features(self.series,self.target)
        for h in range(72):
            self.series[self.target-timedelta(hours=h)]=1e9
        np.testing.assert_array_equal(before,features(self.series,self.target))
    def test_rolling_probability_ignores_unavailable_prices(self):
        before=rolling_probability(self.series,self.target,110)
        for h in range(72):
            self.series[self.target-timedelta(hours=h)]=1e9
        self.assertEqual(before,rolling_probability(self.series,self.target,110))
    def test_missing_historical_hour_excludes_sample(self):
        del self.series[self.target-timedelta(hours=150)]
        self.assertIsNone(features(self.series,self.target))
    def test_auc_ties_and_single_class(self):
        self.assertEqual(auc([0,1],[0.5,0.5]),0.5)
        self.assertEqual(auc([0,1,0,1],[0.1,0.8,0.3,0.9]),1)
        self.assertIsNone(auc([1,1],[0.2,0.3]))
    def test_reliability_bins_count_each_point_once(self):
        y=np.array([0,0,1,0,1,1])
        result=metrics(y,[0,0.1,0.3,0.6,0.9,1])
        self.assertEqual(sum(b["n"] for b in result["reliability"]),6)
        self.assertAlmostEqual(result["brier"],np.mean((np.array([0,0.1,0.3,0.6,0.9,1])-y)**2))
    def test_logistic_learns_without_changing_scaler_at_prediction(self):
        rng=np.random.default_rng(10)
        x=rng.normal(size=(250,3));y=(x[:,0]+x[:,1]>0).astype(int)
        model=Logistic().fit(x,y)
        p=model.predict(x)
        self.assertGreater(auc(y,p),0.98)
        old=model.mean.copy();model.predict(x+1000)
        np.testing.assert_array_equal(old,model.mean)
    def test_test_prices_cannot_change_fitted_model_or_selection(self):
        start=stamp("2025-10-01")
        series={start+timedelta(hours=h):90+60*math.sin(h/7)+25*math.sin(h/170) for h in range(8760)}
        _,a=fit_area(series)
        changed={t:(v+10000 if t>=stamp("2026-07-02") else v) for t,v in series.items()}
        _,b=fit_area(changed)
        self.assertEqual(a["model"],b["model"])
        self.assertEqual(a["strike_eur_mwh"],b["strike_eur_mwh"])
        self.assertEqual(a["validation"],b["validation"])
        self.assertEqual(a["selected"],b["selected"])

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger=Ledger()
        self.addCleanup(self.ledger.close)
    def submit(self,oid="one",area="DK1",issue="2026-07-01",delivery="2026-07-03",**kwargs):
        args={"volume":0.5,"strike":100,"premium":8,"probability":0.3,**kwargs}
        return self.ledger.submit(oid,area,issue,delivery,**args)
    def test_full_lifecycle_and_payout(self):
        self.assertEqual(self.submit(),"OPEN")
        self.assertEqual(self.ledger.settle("one","2026-07-03T01:00",140),20)
        self.assertEqual([e["status"] for e in self.ledger.events()],["SUBMITTED","APPROVED","OPEN","SETTLED"])
    def test_premature_and_repeated_settlement_rejected(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.ledger.settle("one","2026-07-03",140)
        self.ledger.settle("one","2026-07-03T01:00",90)
        with self.assertRaises(ValueError):
            self.ledger.settle("one","2026-07-03T02:00",150)
        self.assertEqual(len(self.ledger.events()),4)
    def test_daily_budget_shared_across_areas(self):
        self.ledger.daily_budget=4
        self.submit()
        self.assertEqual(self.submit("two",area="DK2"),"REJECTED")
        self.assertEqual(self.ledger.orders()[1]["reason"],"daily premium budget")
    def test_open_volume_limit(self):
        self.ledger.max_open_mwh=0.5
        self.submit()
        self.assertEqual(self.submit("two",area="DK2"),"REJECTED")
        self.assertEqual(self.ledger.orders()[1]["reason"],"open volume limit")
    def test_volume_and_kill_switch(self):
        self.assertEqual(self.submit(volume=1),"REJECTED")
        self.ledger.kill_switch=True
        self.assertEqual(self.submit("two",area="DK2"),"REJECTED")
        self.assertEqual(self.ledger.orders()[1]["reason"],"kill switch")
    def test_duplicate_contract_cannot_bypass_limits(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.submit("duplicate")
        self.assertEqual(len(self.ledger.orders()),1)
    def test_invalid_inputs_leave_no_order(self):
        with self.assertRaises(ValueError):
            self.submit(premium=float("nan"))
        self.assertEqual(self.ledger.orders(),[])
    def test_backdated_events_rejected(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.submit("two",area="DK2",issue="2026-06-30")
    def test_settlement_releases_volume(self):
        self.ledger.max_open_mwh=0.5
        self.submit()
        self.ledger.settle("one","2026-07-03T01:00",90)
        self.assertEqual(self.submit("two",issue="2026-07-03T01:00",delivery="2026-07-05"),"OPEN")
    def test_file_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"book.sqlite")
            first=Ledger(p)
            first.submit("one","DK1","2026-07-01","2026-07-03",0.5,100,8,0.3)
            first.close()
            second=Ledger(p)
            try:
                self.assertEqual(second.orders()[0]["status"],"OPEN")
                self.assertEqual(len(second.events()),3)
            finally:
                second.close()

class SimulationTests(unittest.TestCase):
    def forecasts(self):
        return [{"area":a,"delivery":(stamp("2026-07-02")+timedelta(hours=h)).isoformat(),
                 "issue":(stamp("2026-06-30")+timedelta(hours=h)).isoformat(),
                 "probability":0.3,"price":120,"strike":100}
                for h in range(24) for a in ("DK1","DK2")]
    def test_settlement_accounting_and_chronology(self):
        run=simulate(self.forecasts())
        self.assertEqual(run["summary"]["status_counts"],{"SETTLED":15,"REJECTED":33})
        self.assertAlmostEqual(run["summary"]["premium_paid"],60)
        self.assertAlmostEqual(run["summary"]["payout"],150)
        self.assertAlmostEqual(run["daily"][0]["hedged_cost"],48*120+60-150)
        times=[stamp(e["time"]) for e in run["events"]]
        self.assertEqual(times,sorted(times))
    def test_missing_hours_excluded_from_daily_tail(self):
        run=simulate(self.forecasts()[:-1])
        self.assertEqual(run["summary"]["hedged_daily"]["days"],0)
        self.assertEqual(run["daily"],[])
    def test_no_alerts_means_no_hedge(self):
        rows=self.forecasts()
        for row in rows:
            row["probability"]=0.1
        run=simulate(rows)
        self.assertEqual(run["orders"],[])
        self.assertEqual(run["summary"]["net_cost_change"],0)
    def test_no_signal_before_model_lock(self):
        rows=self.forecasts();rows[0]["issue"]="2026-06-29T00:00:00+00:00"
        with self.assertRaises(ValueError):
            simulate(rows)
    def test_tail_mean_uses_whole_worst_days(self):
        s=tail_summary(list(range(1,91)))
        self.assertEqual(s["tail_days"],5)
        self.assertEqual(s["worst_5pct_mean"],88)
    def test_report_data_cannot_close_script_tag(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"report.html"
            render(p,{"test":"</script>"},[],{"orders":[],"events":[]},[])
            self.assertIn(r"\u003c/script>",p.read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()

