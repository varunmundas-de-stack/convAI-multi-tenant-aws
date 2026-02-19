"""
Hierarchy-Aware Push Insights Engine
Generates targeted, actionable nudges per sales hierarchy level:
  SO  → outlet/SKU-level field actions
  ASM → team performance + area gaps
  ZSM → zone trends + ASM comparisons
  NSM → national overview + zone rankings
"""
import sqlite3
import duckdb
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Insight:
    insight_id: str
    tenant_id: str
    hierarchy_level: str          # SO / ASM / ZSM / NSM / all
    title: str
    description: str
    insight_type: str             # trend / anomaly / alert / recommendation / opportunity
    priority: str                 # high / medium / low
    suggested_action: str         # plain-English next step
    suggested_query: str          # pre-filled chat question
    so_code: Optional[str] = None
    asm_code: Optional[str] = None
    zsm_code: Optional[str] = None
    nsm_code: Optional[str] = None
    metric_value: Optional[float] = None
    metric_change_pct: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class HierarchyInsightsEngine:
    """
    Generates hierarchy-aware insights from real DuckDB data.
    Insights are stored in users.db and served via the Flask API.
    """

    PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

    def __init__(self, analytics_db_path: str, users_db_path: str):
        self.analytics_db_path = analytics_db_path
        self.users_db_path = users_db_path

    # ------------------------------------------------------------------ #
    #  PUBLIC: generate & store for a full tenant                          #
    # ------------------------------------------------------------------ #

    def generate_and_store(self, tenant_id: str, schema: str) -> int:
        """
        Generate fresh insights for all hierarchy levels in a tenant.
        Stores results in users.db. Returns count of new insights saved.
        """
        conn = duckdb.connect(self.analytics_db_path, read_only=True)
        all_insights: List[Insight] = []

        try:
            # National / NSM level
            all_insights += self._generate_nsm_insights(conn, tenant_id, schema)
            # Zone / ZSM level
            all_insights += self._generate_zsm_insights(conn, tenant_id, schema)
            # Area / ASM level
            all_insights += self._generate_asm_insights(conn, tenant_id, schema)
            # Territory / SO level
            all_insights += self._generate_so_insights(conn, tenant_id, schema)
        finally:
            conn.close()

        # Expire old insights and store new ones
        self._expire_old_insights(tenant_id)
        saved = self._store_insights(all_insights)
        return saved

    # ------------------------------------------------------------------ #
    #  NSM INSIGHTS  (national trends, zone rankings)                      #
    # ------------------------------------------------------------------ #

    def _generate_nsm_insights(self, conn, tenant_id: str, schema: str) -> List[Insight]:
        insights = []
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')

        # 1. National WoW trend
        try:
            row = conn.execute(f"""
                WITH this_wk AS (
                    SELECT SUM(net_value) AS val
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_date d ON f.date_key = d.date_key
                    WHERE f.invoice_date >= CURRENT_DATE - INTERVAL 7 DAY
                ),
                prev_wk AS (
                    SELECT SUM(net_value) AS val
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_date d ON f.date_key = d.date_key
                    WHERE f.invoice_date >= CURRENT_DATE - INTERVAL 14 DAY
                      AND f.invoice_date < CURRENT_DATE - INTERVAL 7 DAY
                )
                SELECT this_wk.val, prev_wk.val FROM this_wk, prev_wk
            """).fetchone()

            if row and row[0] and row[1] and row[1] > 0:
                this_val, prev_val = float(row[0]), float(row[1])
                chg = (this_val - prev_val) / prev_val * 100
                priority = 'high' if abs(chg) > 15 else 'medium'
                direction = 'up' if chg > 0 else 'DOWN'
                insights.append(Insight(
                    insight_id=f"nsm_national_wow_{tenant_id}_{today_str}",
                    tenant_id=tenant_id,
                    hierarchy_level='NSM',
                    title=f"National sales {direction} {abs(chg):.1f}% vs last week",
                    description=(
                        f"This week: Rs {this_val:,.0f}  |  Last week: Rs {prev_val:,.0f}. "
                        f"{'Strong momentum — maintain focus.' if chg > 0 else 'Needs immediate review across zones.'}"
                    ),
                    insight_type='trend',
                    priority=priority,
                    suggested_action='Review zone-wise breakdown and identify lagging areas.',
                    suggested_query='Weekly sales trend for last 6 weeks',
                    metric_value=this_val,
                    metric_change_pct=round(chg, 2),
                    created_at=now,
                    expires_at=now + timedelta(days=2),
                ))
        except Exception as e:
            print(f"[Insights] NSM WoW trend error: {e}")

        # 2. Top and bottom zone this month
        try:
            rows = conn.execute(f"""
                SELECT g.zone_name, SUM(f.net_value) AS zone_sales
                FROM {schema}.fact_secondary_sales f
                JOIN {schema}.dim_geography g ON f.geography_key = g.geography_key
                WHERE EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                GROUP BY g.zone_name
                ORDER BY zone_sales DESC
            """).fetchall()

            if rows and len(rows) >= 2:
                top_zone, top_val = rows[0][0], float(rows[0][1])
                bot_zone, bot_val = rows[-1][0], float(rows[-1][1])
                insights.append(Insight(
                    insight_id=f"nsm_zone_rank_{tenant_id}_{today_str}",
                    tenant_id=tenant_id,
                    hierarchy_level='NSM',
                    title=f"Zone ranking: {top_zone} leads, {bot_zone} lags",
                    description=(
                        f"This month — Top zone: {top_zone} (Rs {top_val:,.0f})  |  "
                        f"Bottom zone: {bot_zone} (Rs {bot_val:,.0f}). "
                        f"Gap of Rs {(top_val - bot_val):,.0f}."
                    ),
                    insight_type='recommendation',
                    priority='medium',
                    suggested_action=f'Conduct review call with {bot_zone} ZSM. Share best practices from {top_zone}.',
                    suggested_query='Sales by state this month',
                    metric_value=bot_val,
                    data={'top_zone': top_zone, 'bottom_zone': bot_zone},
                    created_at=now,
                    expires_at=now + timedelta(days=3),
                ))
        except Exception as e:
            print(f"[Insights] NSM zone rank error: {e}")

        # 3. National anomaly detection (2-sigma on daily sales)
        try:
            row = conn.execute(f"""
                WITH daily AS (
                    SELECT f.invoice_date, SUM(f.net_value) AS day_val
                    FROM {schema}.fact_secondary_sales f
                    WHERE f.invoice_date >= CURRENT_DATE - INTERVAL 30 DAY
                    GROUP BY f.invoice_date
                ),
                stats AS (SELECT AVG(day_val) AS avg_val, STDDEV(day_val) AS std_val FROM daily),
                yesterday AS (
                    SELECT day_val FROM daily
                    WHERE invoice_date = (SELECT MAX(invoice_date) FROM daily)
                )
                SELECT y.day_val, s.avg_val, s.std_val
                FROM yesterday y, stats s
                WHERE ABS(y.day_val - s.avg_val) > 1.8 * s.std_val
            """).fetchone()

            if row:
                day_val, avg_val, std_val = float(row[0]), float(row[1]), float(row[2])
                chg = (day_val - avg_val) / avg_val * 100
                direction = 'spike' if day_val > avg_val else 'drop'
                insights.append(Insight(
                    insight_id=f"nsm_anomaly_{tenant_id}_{today_str}",
                    tenant_id=tenant_id,
                    hierarchy_level='NSM',
                    title=f"Sales {direction} alert — {abs(chg):.0f}% from 30-day average",
                    description=(
                        f"Yesterday's national sales: Rs {day_val:,.0f} vs "
                        f"30-day avg of Rs {avg_val:,.0f}. "
                        f"This is a statistically unusual {'high' if day_val > avg_val else 'low'}."
                    ),
                    insight_type='anomaly',
                    priority='high',
                    suggested_action='Identify which zones/brands drove this deviation.',
                    suggested_query='Why did sales change?',
                    metric_value=day_val,
                    metric_change_pct=round(chg, 2),
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                ))
        except Exception as e:
            print(f"[Insights] NSM anomaly error: {e}")

        return insights

    # ------------------------------------------------------------------ #
    #  ZSM INSIGHTS  (zone trend, ASM team performance)                   #
    # ------------------------------------------------------------------ #

    def _generate_zsm_insights(self, conn, tenant_id: str, schema: str) -> List[Insight]:
        insights = []
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')

        # Get all ZSMs
        zsms = conn.execute(f"""
            SELECT DISTINCT zsm_code, zsm_name FROM {schema}.dim_sales_hierarchy
            WHERE zsm_code IS NOT NULL
        """).fetchall()

        for zsm_code, zsm_name in zsms:
            # 1. Zone WoW performance
            try:
                row = conn.execute(f"""
                    WITH this_wk AS (
                        SELECT SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        WHERE sh.zsm_code = '{zsm_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 7 DAY
                    ),
                    prev_wk AS (
                        SELECT SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        WHERE sh.zsm_code = '{zsm_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 14 DAY
                          AND f.invoice_date < CURRENT_DATE - INTERVAL 7 DAY
                    )
                    SELECT this_wk.val, prev_wk.val FROM this_wk, prev_wk
                """).fetchone()

                if row and row[0] and row[1] and row[1] > 0:
                    this_val, prev_val = float(row[0]), float(row[1])
                    chg = (this_val - prev_val) / prev_val * 100
                    priority = 'high' if chg < -10 else ('medium' if abs(chg) > 5 else 'low')
                    direction = 'up' if chg > 0 else 'DOWN'
                    insights.append(Insight(
                        insight_id=f"zsm_wow_{tenant_id}_{zsm_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='ZSM',
                        zsm_code=zsm_code,
                        title=f"Zone {direction} {abs(chg):.1f}% vs last week",
                        description=(
                            f"{zsm_name}'s zone: this week Rs {this_val:,.0f} vs "
                            f"Rs {prev_val:,.0f} last week ({chg:+.1f}%). "
                            f"{'Good trajectory.' if chg > 0 else 'Action needed.'}"
                        ),
                        insight_type='trend',
                        priority=priority,
                        suggested_action='Review ASM-wise split to find where gap is concentrated.' if chg < 0 else 'Identify and replicate what is working.',
                        suggested_query='Weekly sales trend for last 6 weeks',
                        metric_value=this_val,
                        metric_change_pct=round(chg, 2),
                        created_at=now,
                        expires_at=now + timedelta(days=2),
                    ))
            except Exception as e:
                print(f"[Insights] ZSM WoW error {zsm_code}: {e}")

            # 2. ASM performance ranking within zone
            try:
                rows = conn.execute(f"""
                    SELECT sh.asm_code, sh.asm_name, SUM(f.net_value) AS asm_sales
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                    WHERE sh.zsm_code = '{zsm_code}'
                      AND EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                    GROUP BY sh.asm_code, sh.asm_name
                    ORDER BY asm_sales DESC
                """).fetchall()

                if rows and len(rows) >= 2:
                    top_asm_name = rows[0][1]
                    bot_asm_code = rows[-1][0]
                    bot_asm_name = rows[-1][1]
                    bot_val = float(rows[-1][2])
                    top_val = float(rows[0][2])
                    under_count = sum(1 for r in rows if float(r[2]) < (sum(float(x[2]) for x in rows) / len(rows)))

                    insights.append(Insight(
                        insight_id=f"zsm_asm_perf_{tenant_id}_{zsm_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='ZSM',
                        zsm_code=zsm_code,
                        title=f"{under_count} of {len(rows)} ASMs below zone average this month",
                        description=(
                            f"Top ASM: {top_asm_name} (Rs {top_val:,.0f})  |  "
                            f"Needs attention: {bot_asm_name} (Rs {bot_val:,.0f}). "
                            f"Gap: Rs {(top_val - bot_val):,.0f}."
                        ),
                        insight_type='alert' if under_count > len(rows) // 2 else 'recommendation',
                        priority='high' if under_count > len(rows) // 2 else 'medium',
                        suggested_action=f'Schedule review with {bot_asm_name}. Check their SO team coverage.',
                        suggested_query='Top distributors by sales value',
                        metric_value=bot_val,
                        data={'under_count': under_count, 'total_asms': len(rows), 'bottom_asm': bot_asm_name},
                        created_at=now,
                        expires_at=now + timedelta(days=3),
                    ))
            except Exception as e:
                print(f"[Insights] ZSM ASM perf error {zsm_code}: {e}")

        return insights

    # ------------------------------------------------------------------ #
    #  ASM INSIGHTS  (SO team, brand gaps, district performance)           #
    # ------------------------------------------------------------------ #

    def _generate_asm_insights(self, conn, tenant_id: str, schema: str) -> List[Insight]:
        insights = []
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')

        asms = conn.execute(f"""
            SELECT DISTINCT asm_code, asm_name FROM {schema}.dim_sales_hierarchy
            WHERE asm_code IS NOT NULL
        """).fetchall()

        for asm_code, asm_name in asms:
            # 1. SO performance ranking within area
            try:
                rows = conn.execute(f"""
                    SELECT sh.so_code, sh.so_name, SUM(f.net_value) AS so_sales
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                    WHERE sh.asm_code = '{asm_code}'
                      AND EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                    GROUP BY sh.so_code, sh.so_name
                    ORDER BY so_sales DESC
                """).fetchall()

                if rows and len(rows) >= 2:
                    avg_sales = sum(float(r[2]) for r in rows) / len(rows)
                    under_target = [(r[0], r[1], float(r[2])) for r in rows if float(r[2]) < avg_sales]
                    top_so = rows[0]

                    insights.append(Insight(
                        insight_id=f"asm_so_perf_{tenant_id}_{asm_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='ASM',
                        asm_code=asm_code,
                        title=f"{len(under_target)} of {len(rows)} SOs below area average",
                        description=(
                            f"Area average: Rs {avg_sales:,.0f}/month. "
                            f"Best SO: {top_so[1]} (Rs {float(top_so[2]):,.0f}). "
                            + (f"Lagging: {under_target[0][1]} (Rs {under_target[0][2]:,.0f})." if under_target else "All SOs performing well.")
                        ),
                        insight_type='alert' if len(under_target) > len(rows) // 2 else 'recommendation',
                        priority='high' if len(under_target) >= len(rows) // 2 else 'medium',
                        suggested_action=f"Coach underperforming SOs. Check outlet coverage and call frequency." if under_target else "Sustain current momentum.",
                        suggested_query='Top distributors by sales value',
                        metric_value=avg_sales,
                        data={'total_sos': len(rows), 'under_target': len(under_target)},
                        created_at=now,
                        expires_at=now + timedelta(days=3),
                    ))
            except Exception as e:
                print(f"[Insights] ASM SO perf error {asm_code}: {e}")

            # 2. Brand gap — which brand is declining in this area
            try:
                rows = conn.execute(f"""
                    WITH this_wk AS (
                        SELECT p.brand_name, SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        JOIN {schema}.dim_product p ON f.product_key = p.product_key
                        WHERE sh.asm_code = '{asm_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 7 DAY
                        GROUP BY p.brand_name
                    ),
                    prev_wk AS (
                        SELECT p.brand_name, SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        JOIN {schema}.dim_product p ON f.product_key = p.product_key
                        WHERE sh.asm_code = '{asm_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 14 DAY
                          AND f.invoice_date < CURRENT_DATE - INTERVAL 7 DAY
                        GROUP BY p.brand_name
                    )
                    SELECT t.brand_name,
                           t.val AS this_val,
                           p.val AS prev_val,
                           ((t.val - p.val) / p.val * 100) AS chg
                    FROM this_wk t
                    JOIN prev_wk p ON t.brand_name = p.brand_name
                    WHERE p.val > 0
                    ORDER BY chg ASC
                    LIMIT 1
                """).fetchone()

                if rows and rows[3] < -10:
                    brand, this_val, prev_val, chg = rows[0], float(rows[1]), float(rows[2]), float(rows[3])
                    insights.append(Insight(
                        insight_id=f"asm_brand_gap_{tenant_id}_{asm_code}_{brand.replace(' ', '_')}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='ASM',
                        asm_code=asm_code,
                        title=f"Brand alert: {brand} down {abs(chg):.0f}% in your area",
                        description=(
                            f"{brand} sales this week: Rs {this_val:,.0f} vs "
                            f"Rs {prev_val:,.0f} last week ({chg:.1f}%). "
                            f"Check if it is a distribution issue or offtake problem."
                        ),
                        insight_type='alert',
                        priority='high' if chg < -20 else 'medium',
                        suggested_action=f"Ask SOs to check {brand} shelf availability and push sell-in.",
                        suggested_query=f'Show top 5 brands by sales',
                        metric_value=this_val,
                        metric_change_pct=round(chg, 2),
                        data={'brand': brand},
                        created_at=now,
                        expires_at=now + timedelta(days=2),
                    ))
            except Exception as e:
                print(f"[Insights] ASM brand gap error {asm_code}: {e}")

        return insights

    # ------------------------------------------------------------------ #
    #  SO INSIGHTS  (outlet-level, SKU actions)                            #
    # ------------------------------------------------------------------ #

    def _generate_so_insights(self, conn, tenant_id: str, schema: str) -> List[Insight]:
        insights = []
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')

        sos = conn.execute(f"""
            SELECT DISTINCT so_code, so_name FROM {schema}.dim_sales_hierarchy
            WHERE so_code IS NOT NULL
        """).fetchall()

        for so_code, so_name in sos:
            # 1. Personal WoW performance
            try:
                row = conn.execute(f"""
                    WITH this_wk AS (
                        SELECT SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        WHERE sh.so_code = '{so_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 7 DAY
                    ),
                    prev_wk AS (
                        SELECT SUM(f.net_value) AS val
                        FROM {schema}.fact_secondary_sales f
                        JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                        WHERE sh.so_code = '{so_code}'
                          AND f.invoice_date >= CURRENT_DATE - INTERVAL 14 DAY
                          AND f.invoice_date < CURRENT_DATE - INTERVAL 7 DAY
                    )
                    SELECT this_wk.val, prev_wk.val FROM this_wk, prev_wk
                """).fetchone()

                if row and row[0] and row[1] and row[1] > 0:
                    this_val, prev_val = float(row[0]), float(row[1])
                    chg = (this_val - prev_val) / prev_val * 100
                    priority = 'high' if chg < -15 else ('medium' if abs(chg) > 5 else 'low')
                    direction = 'up' if chg > 0 else 'DOWN'
                    insights.append(Insight(
                        insight_id=f"so_wow_{tenant_id}_{so_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='SO',
                        so_code=so_code,
                        title=f"Your sales {direction} {abs(chg):.1f}% vs last week",
                        description=(
                            f"This week: Rs {this_val:,.0f}  |  Last week: Rs {prev_val:,.0f}. "
                            + ("Great momentum — keep pushing!" if chg > 0 else "You need to increase outlet visits and push top SKUs.")
                        ),
                        insight_type='trend',
                        priority=priority,
                        suggested_action='Increase outlet visit frequency for slow accounts.' if chg < 0 else 'Identify your top outlets and upsell.',
                        suggested_query='Weekly sales trend for last 6 weeks',
                        metric_value=this_val,
                        metric_change_pct=round(chg, 2),
                        created_at=now,
                        expires_at=now + timedelta(days=2),
                    ))
            except Exception as e:
                print(f"[Insights] SO WoW error {so_code}: {e}")

            # 2. Top opportunity brand — lowest share in territory
            try:
                rows = conn.execute(f"""
                    SELECT p.brand_name, SUM(f.net_value) AS brand_sales
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                    JOIN {schema}.dim_product p ON f.product_key = p.product_key
                    WHERE sh.so_code = '{so_code}'
                      AND EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                    GROUP BY p.brand_name
                    ORDER BY brand_sales ASC
                    LIMIT 1
                """).fetchone()

                if rows:
                    weak_brand, weak_val = rows[0], float(rows[1])
                    insights.append(Insight(
                        insight_id=f"so_opportunity_{tenant_id}_{so_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='SO',
                        so_code=so_code,
                        title=f"Growth opportunity: push {weak_brand} harder",
                        description=(
                            f"{weak_brand} is your lowest-selling brand this month (Rs {weak_val:,.0f}). "
                            f"Increase distribution coverage and visibility at your outlets."
                        ),
                        insight_type='opportunity',
                        priority='medium',
                        suggested_action=f"At every outlet visit today, ensure {weak_brand} is stocked and visible.",
                        suggested_query=f'Show top 5 brands by sales',
                        metric_value=weak_val,
                        data={'brand': weak_brand},
                        created_at=now,
                        expires_at=now + timedelta(days=3),
                    ))
            except Exception as e:
                print(f"[Insights] SO opportunity error {so_code}: {e}")

            # 3. Top channel for this SO
            try:
                rows = conn.execute(f"""
                    SELECT ch.channel_name, SUM(f.net_value) AS ch_sales
                    FROM {schema}.fact_secondary_sales f
                    JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.sales_hierarchy_key
                    JOIN {schema}.dim_channel ch ON f.channel_key = ch.channel_key
                    WHERE sh.so_code = '{so_code}'
                      AND EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                    GROUP BY ch.channel_name
                    ORDER BY ch_sales DESC
                    LIMIT 1
                """).fetchone()

                if rows:
                    top_channel, ch_val = rows[0], float(rows[1])
                    insights.append(Insight(
                        insight_id=f"so_channel_{tenant_id}_{so_code}_{today_str}",
                        tenant_id=tenant_id,
                        hierarchy_level='SO',
                        so_code=so_code,
                        title=f"{top_channel} is your strongest channel — double down",
                        description=(
                            f"Your {top_channel} channel contributed Rs {ch_val:,.0f} this month. "
                            f"This is your biggest opportunity. Increase call frequency here."
                        ),
                        insight_type='recommendation',
                        priority='low',
                        suggested_action=f"Plan 2 extra visits this week to {top_channel} outlets.",
                        suggested_query='Compare sales by channel',
                        metric_value=ch_val,
                        data={'channel': top_channel},
                        created_at=now,
                        expires_at=now + timedelta(days=3),
                    ))
            except Exception as e:
                print(f"[Insights] SO channel error {so_code}: {e}")

        return insights

    # ------------------------------------------------------------------ #
    #  STORAGE & RETRIEVAL                                                  #
    # ------------------------------------------------------------------ #

    def _expire_old_insights(self, tenant_id: str):
        """Mark expired insights as inactive"""
        conn = sqlite3.connect(self.users_db_path)
        conn.execute("""
            UPDATE insights SET is_active = 0
            WHERE tenant_id = ? AND (expires_at < CURRENT_TIMESTAMP OR is_active = 1)
              AND expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
        """, (tenant_id,))
        conn.commit()
        conn.close()

    def _store_insights(self, insights: List[Insight]) -> int:
        """Upsert insights into users.db"""
        if not insights:
            return 0
        conn = sqlite3.connect(self.users_db_path)
        saved = 0
        for ins in insights:
            try:
                conn.execute("""
                    INSERT INTO insights (
                        insight_id, tenant_id, hierarchy_level,
                        so_code, asm_code, zsm_code, nsm_code,
                        title, description, insight_type, priority,
                        metric_value, metric_change_pct,
                        suggested_action, suggested_query, data_json,
                        created_at, expires_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(insight_id) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        metric_value=excluded.metric_value,
                        metric_change_pct=excluded.metric_change_pct,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at,
                        is_active=1
                """, (
                    ins.insight_id, ins.tenant_id, ins.hierarchy_level,
                    ins.so_code, ins.asm_code, ins.zsm_code, ins.nsm_code,
                    ins.title, ins.description, ins.insight_type, ins.priority,
                    ins.metric_value, ins.metric_change_pct,
                    ins.suggested_action, ins.suggested_query,
                    json.dumps(ins.data or {}),
                    ins.created_at.isoformat() if ins.created_at else None,
                    ins.expires_at.isoformat() if ins.expires_at else None,
                ))
                saved += 1
            except Exception as e:
                print(f"[Insights] Store error {ins.insight_id}: {e}")
        conn.commit()
        conn.close()
        return saved

    def get_insights_for_user(self, user_id: int, hierarchy_level: str,
                               tenant_id: str,
                               so_code: str = None, asm_code: str = None,
                               zsm_code: str = None, nsm_code: str = None,
                               limit: int = 10) -> List[Dict]:
        """
        Fetch active insights relevant to a specific user.
        Hierarchy scoping: SO sees own SO insights + ASM/ZSM/NSM summaries.
        """
        conn = sqlite3.connect(self.users_db_path)
        conn.row_factory = sqlite3.Row

        # Build visibility filter based on role
        # Each level sees their own level + higher levels (for context)
        level_order = ['SO', 'ASM', 'ZSM', 'NSM', 'all']
        try:
            user_level_idx = level_order.index(hierarchy_level)
        except ValueError:
            user_level_idx = len(level_order) - 1  # admin/analyst sees all

        visible_levels = level_order[user_level_idx:]  # own level and above

        placeholders = ','.join('?' * len(visible_levels))
        params = [tenant_id] + visible_levels

        # Add hierarchy code filter so users only see their own hierarchy's data
        code_filters = []
        if hierarchy_level == 'SO' and so_code:
            code_filters.append(f"(hierarchy_level != 'SO' OR so_code = '{so_code}')")
        if hierarchy_level in ('SO', 'ASM') and asm_code:
            code_filters.append(f"(hierarchy_level NOT IN ('SO', 'ASM') OR asm_code = '{asm_code}')")
        if hierarchy_level in ('SO', 'ASM', 'ZSM') and zsm_code:
            code_filters.append(f"(hierarchy_level NOT IN ('SO', 'ASM', 'ZSM') OR zsm_code = '{zsm_code}')")

        code_clause = (' AND ' + ' AND '.join(code_filters)) if code_filters else ''

        rows = conn.execute(f"""
            SELECT i.*,
                   CASE WHEN ir.insight_id IS NOT NULL THEN 1 ELSE 0 END AS is_read
            FROM insights i
            LEFT JOIN insight_reads ir ON i.insight_id = ir.insight_id AND ir.user_id = ?
            WHERE i.tenant_id = ?
              AND i.is_active = 1
              AND i.hierarchy_level IN ({placeholders})
              {code_clause}
            ORDER BY
                CASE i.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                i.created_at DESC
            LIMIT ?
        """, [user_id] + params + [limit]).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    def mark_read(self, insight_id: str, user_id: int):
        """Mark an insight as read for a user"""
        conn = sqlite3.connect(self.users_db_path)
        conn.execute("""
            INSERT OR IGNORE INTO insight_reads (insight_id, user_id) VALUES (?, ?)
        """, (insight_id, user_id))
        conn.commit()
        conn.close()

    def get_unread_count(self, user_id: int, hierarchy_level: str,
                          tenant_id: str,
                          so_code: str = None, asm_code: str = None,
                          zsm_code: str = None) -> int:
        """Return count of unread insights for a user"""
        insights = self.get_insights_for_user(
            user_id, hierarchy_level, tenant_id,
            so_code=so_code, asm_code=asm_code, zsm_code=zsm_code
        )
        return sum(1 for i in insights if not i['is_read'])
