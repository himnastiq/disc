'use client';

import React, { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  ShieldAlert,
  Info,
  CheckCircle2,
  XCircle,
  SlidersHorizontal,
} from 'lucide-react';
import { useMetrics } from '@/lib/api/hooks';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';

export interface EvaluationTabProps {
  type: string;
}

export interface EvaluationMetricsPayload {
  git_sha?: string;
  config_hash?: string;
  is_synthetic?: boolean;
  synthetic_demo?: boolean;
  provenance_banner?: string | null;
  dataset_variant?: string;
  protocol?: {
    split_strategy?: string;
    split_ratio?: number;
    evaluated_test_users?: number;
    total_test_users?: number;
    bootstrap_resamples?: number;
    positive_threshold?: number;
    dual_protocol?: boolean;
  };
  protocols?: {
    impression_ranking?: {
      evaluated_impressions?: number;
      models?: Record<string, Record<string, unknown>>;
    };
    retrieval?: {
      models?: Record<string, Record<string, Record<string, unknown>>>;
    };
  };
  models?: Record<string, Record<string, Record<string, unknown>>>;
  cold_start_curves?: Record<string, Record<string, Record<string, number>>>;
}

export function formatMetric(val: unknown, decimals: number = 4): string {
  if (val === null || val === undefined || typeof val !== 'number' || Number.isNaN(val)) return '—';
  return val.toFixed(decimals);
}

export function formatCi(ci: unknown, decimals: number = 4): string {
  if (!ci || !Array.isArray(ci) || ci.length < 2) return '';
  return `[${formatMetric(ci[0], decimals)}, ${formatMetric(ci[1], decimals)}]`;
}

function formatPercent(val: unknown): string {
  if (typeof val !== 'number' || Number.isNaN(val)) return '—';
  return Math.round(val * 100) + '%';
}

export function EvaluationTab({ type }: EvaluationTabProps) {
  const { data: metricsData, isLoading, isError, refetch } = useMetrics(type);

  const [selectedK, setSelectedK] = useState<number>(10);
  const [selectedChartMetric, setSelectedChartMetric] = useState<string>('ndcg');
  const [selectedCurveMetric, setSelectedCurveMetric] = useState<'hit_rate@10' | 'ndcg@10' | 'recall@10'>('ndcg@10');

  const rawData = metricsData as unknown as EvaluationMetricsPayload | undefined;

  // Identify model name (exclude baseline names 'popularity' and 'random')
  const modelsDict = rawData?.models || rawData?.protocols?.retrieval?.models || {};
  const modelKeys = Object.keys(modelsDict);
  const modelName = modelKeys.find((k) => k !== 'popularity' && k !== 'random') || 'model';

  const impressionModels = rawData?.protocols?.impression_ranking?.models;
  const impressionKeys = impressionModels ? Object.keys(impressionModels) : [];
  const impressionModelName = impressionKeys.find((k) => k !== 'popularity' && k !== 'random') || 'model';

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-14 w-full bg-[var(--color-surface)]" />
        <Skeleton className="h-64 w-full bg-[var(--color-surface)]" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-56 bg-[var(--color-surface)]" />
          <Skeleton className="h-56 bg-[var(--color-surface)]" />
        </div>
      </div>
    );
  }

  if (isError || !rawData) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <ErrorState
          title="Evaluation metrics unavailable"
          message={`Failed to retrieve verified evaluation metrics for ${type}.`}
          onRetry={refetch}
        />
      </div>
    );
  }

  const isDualProtocol = Boolean(rawData.protocol?.dual_protocol || rawData.protocols?.impression_ranking);
  const currentModelData = modelsDict[modelName]?.[String(selectedK)] || {};
  const popularityData = modelsDict['popularity']?.[String(selectedK)] || {};
  const randomData = modelsDict['random']?.[String(selectedK)] || {};

  // Cold start curves
  const coldStartCurves = rawData.cold_start_curves || {};
  const historySteps = ['0', '1', '2', '3', '5', '10', '20'];

  return (
    <div className="space-y-6">
      {/* 1. Provenance & Dataset Banner */}
      {(rawData.is_synthetic || rawData.synthetic_demo || rawData.provenance_banner) && (
        <div
          role="status"
          aria-label="Dataset provenance notice"
          className="rounded-[var(--radius-card)] border border-amber-600/30 bg-amber-950/20 p-4 flex items-start gap-3 text-xs"
        >
          <ShieldAlert className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-amber-200">
              Provenance Notice: {rawData.dataset_variant ? `Variant ${rawData.dataset_variant}` : 'Benchmark Data'}
            </h4>
            <p className="text-amber-300/80 mt-0.5">
              {rawData.provenance_banner ||
                'This domain uses a controlled evaluation subset for rapid verification. All metric values originate strictly from metrics.json.'}
            </p>
          </div>
        </div>
      )}

      {/* 2. Protocol Header Card */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[var(--color-border)] pb-3">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-[var(--color-accent)]" />
            <h3 className="font-bold text-sm text-[var(--color-text)]">
              Evaluation Protocol & Verification
            </h3>
          </div>
          <div className="text-[12px] text-[var(--color-text-muted)] font-mono">
            SHA: {rawData.git_sha ? String(rawData.git_sha).slice(0, 8) : '—'} · Hash: {rawData.config_hash ? String(rawData.config_hash).slice(0, 8) : '—'}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[12px]">
          <div>
            <span className="text-[var(--color-text-muted)] block">Split Strategy</span>
            <span className="font-semibold text-[var(--color-text)] capitalize">
              {!rawData.protocol?.split_strategy && (rawData.protocol?.split_ratio == null || typeof rawData.protocol?.split_ratio !== 'number')
                ? '—'
                : `${rawData.protocol?.split_strategy ?? '—'} (${formatPercent(rawData.protocol?.split_ratio)} train)`}
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)] block">Test Users Evaluated</span>
            <span className="font-semibold text-[var(--color-text)] tabular-nums">
              {rawData.protocol?.evaluated_test_users ?? rawData.protocol?.total_test_users ?? '—'} users
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)] block">Confidence Intervals</span>
            <span className="font-semibold text-[var(--color-text)]">
              95% Bootstrap ({rawData.protocol?.bootstrap_resamples || 500} resamples)
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)] block">Positive Threshold</span>
            <span className="font-semibold text-[var(--color-text)] tabular-nums">
              {typeof rawData.protocol?.positive_threshold === 'number' ? (
                <>&ge; {rawData.protocol.positive_threshold}</>
              ) : (
                (rawData.protocol?.positive_threshold ?? '—')
              )}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Dual Protocol Impression Ranking (MIND Protocol for Articles) */}
      {isDualProtocol && rawData.protocols?.impression_ranking && (
        <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[var(--color-text)] flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-[var(--color-accent)]" />
                <span>Protocol (a): Impression Candidate Ranking (MIND Benchmark)</span>
              </h3>
              <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
                Evaluates candidate ranking within each impression list (1 positive click vs negative impressions).
              </p>
            </div>
            <span className="text-[12px] text-[var(--color-text-muted)] tabular-nums font-mono">
              {rawData.protocols.impression_ranking.evaluated_impressions} impressions
            </span>
          </div>

          <div
            tabIndex={0}
            role="region"
            aria-label="Impression ranking metrics table"
            className="overflow-x-auto focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)]"
          >
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] font-semibold">
                  <th className="py-2 pr-4">Model</th>
                  <th className="py-2 px-3">AUC (95% CI)</th>
                  <th className="py-2 px-3">MRR (95% CI)</th>
                  <th className="py-2 px-3">nDCG@5 (95% CI)</th>
                  <th className="py-2 px-3">nDCG@10 (95% CI)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]/60">
                {['random', 'popularity', impressionModelName].map((mKey) => {
                  const mData = rawData.protocols?.impression_ranking?.models?.[mKey];
                  if (!mData) return null;
                  const isPrimary = mKey === impressionModelName;
                  return (
                    <tr
                      key={mKey}
                      className={isPrimary ? 'bg-[var(--color-elevated)]/60 font-semibold' : ''}
                    >
                      <td className="py-2.5 pr-4 flex items-center gap-1.5 capitalize">
                        {isPrimary && <span className="h-2 w-2 rounded-full bg-[var(--color-accent)]" />}
                        <span>{mKey === 'tfidf_profile' ? 'TF-IDF Profile' : mKey}</span>
                      </td>
                      <td className="py-2.5 px-3 tabular-nums">
                        {formatMetric(mData.auc)} <span className="text-[12px] text-[var(--color-text-muted)]">{formatCi(mData.auc_ci95)}</span>
                      </td>
                      <td className="py-2.5 px-3 tabular-nums">
                        {formatMetric(mData.mrr)} <span className="text-[12px] text-[var(--color-text-muted)]">{formatCi(mData.mrr_ci95)}</span>
                      </td>
                      <td className="py-2.5 px-3 tabular-nums">
                        {formatMetric(mData['ndcg@5'])} <span className="text-[12px] text-[var(--color-text-muted)]">{formatCi(mData['ndcg@5_ci95'])}</span>
                      </td>
                      <td className="py-2.5 px-3 tabular-nums">
                        {formatMetric(mData['ndcg@10'])} <span className="text-[12px] text-[var(--color-text-muted)]">{formatCi(mData['ndcg@10_ci95'])}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. Main Metrics Comparison Table across K */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-[var(--color-text)] flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-[var(--color-accent)]" />
              <span>{isDualProtocol ? 'Protocol (b): Top-K Retrieval from Candidate Pool' : 'Ranking & Retrieval Benchmarks'}</span>
            </h3>
            <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
              Verified metric estimates with bootstrap 95% confidence intervals against baseline models.
            </p>
          </div>

          {/* k Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <SlidersHorizontal className="h-3 w-3" /> k:
            </span>
            <div className="inline-flex rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg)] p-0.5 text-xs">
              {[5, 10, 20].map((kVal) => (
                <button
                  key={kVal}
                  type="button"
                  onClick={() => setSelectedK(kVal)}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-[4px] cursor-pointer tabular-nums transition-colors ${
                    selectedK === kVal
                      ? 'bg-[var(--color-elevated)] text-[var(--color-accent-text)]'
                      : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                  }`}
                >
                  {kVal}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Headline Metrics Table */}
        <div
          tabIndex={0}
          role="region"
          aria-label="Top-K ranking metrics table"
          className="overflow-x-auto focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)]"
        >
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] font-semibold">
                <th className="py-2.5 pr-4">Metric @ {selectedK}</th>
                <th className="py-2.5 px-3">Random</th>
                <th className="py-2.5 px-3">Popularity (95% CI)</th>
                <th className="py-2.5 px-3 text-[var(--color-accent-text)]">
                  {modelName.toUpperCase()} (Personalized)
                </th>
                <th className="py-2.5 px-3">Statistical Separation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]/60">
              {[
                { key: 'hit_rate', label: 'Hit Rate' },
                { key: 'ndcg', label: 'nDCG' },
                { key: 'recall', label: 'Recall' },
                { key: 'precision', label: 'Precision' },
                { key: 'map', label: 'MAP' },
              ].map(({ key, label }) => {
                const randVal = randomData[key];
                const popVal = popularityData[key];
                const popCi = popularityData[`${key}_ci95`];
                const modVal = currentModelData[key];
                const modCi = currentModelData[`${key}_ci95`];

                // Check separation if CI lower bound of model > CI upper bound of popularity
                const isSeparated =
                  Array.isArray(modCi) && Array.isArray(popCi) && modCi.length >= 2 && popCi.length >= 2
                    ? Number(modCi[0]) > Number(popCi[1])
                    : false;

                return (
                  <tr key={key} className="hover:bg-[var(--color-elevated)]/40 transition-colors">
                    <td className="py-2.5 pr-4 font-semibold text-[var(--color-text)]">
                      {label}@{selectedK}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-[var(--color-text-muted)]">
                      {formatMetric(randVal)}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums">
                      <span className="text-[var(--color-text)]">{formatMetric(popVal)}</span>{' '}
                      <span className="text-[12px] text-[var(--color-text-muted)]">{formatCi(popCi)}</span>
                    </td>
                    <td className="py-2.5 px-3 tabular-nums font-bold text-[var(--color-text)]">
                      <span>{formatMetric(modVal)}</span>{' '}
                      <span className="text-[12px] text-[var(--color-accent-text)]">{formatCi(modCi)}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      {isSeparated ? (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 px-2 py-0.5 text-[12px] font-semibold">
                          <CheckCircle2 className="h-3 w-3" /> CIs Separate
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-zinc-900 text-zinc-400 border border-zinc-800 px-2 py-0.5 text-[12px] font-semibold">
                          <XCircle className="h-3 w-3 text-zinc-500" /> Overlap / Tied
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Interactive Bar Chart & Cold-Start Line Chart */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Metric Comparison Bar Chart */}
        <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-[var(--color-text)] uppercase tracking-wider">
              Metric Comparison @ {selectedK}
            </h4>
            <select
              aria-label="Select metric for bar chart"
              value={selectedChartMetric}
              onChange={(e) => setSelectedChartMetric(e.target.value)}
              className="h-7 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg)] px-2 text-xs text-[var(--color-text)] focus:outline-none"
            >
              <option value="hit_rate">Hit Rate</option>
              <option value="ndcg">nDCG</option>
              <option value="recall">Recall</option>
              <option value="precision">Precision</option>
              <option value="map">MAP</option>
            </select>
          </div>

          {/* Bar Chart Visualization */}
          {(() => {
            const mVal = Number(currentModelData[selectedChartMetric]) || 0;
            const pVal = Number(popularityData[selectedChartMetric]) || 0;
            const rVal = Number(randomData[selectedChartMetric]) || 0;
            const maxVal = Math.max(mVal, pVal, rVal, 0.0001);

            return (
              <div className="space-y-3 pt-2">
                {[
                  { label: modelName.toUpperCase(), value: mVal, color: 'bg-[var(--color-accent)]' },
                  { label: 'Popularity', value: pVal, color: 'bg-zinc-500' },
                  { label: 'Random', value: rVal, color: 'bg-zinc-700' },
                ].map((bar) => {
                  const widthPercent = Math.min(100, Math.round((bar.value / maxVal) * 100));
                  return (
                    <div key={bar.label} className="space-y-1">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-[var(--color-text)]">{bar.label}</span>
                        <span className="tabular-nums font-mono text-[var(--color-text-secondary)]">
                          {formatMetric(bar.value)}
                        </span>
                      </div>
                      <div className="h-3 w-full bg-[var(--color-bg)] rounded-[3px] overflow-hidden border border-[var(--color-border)]">
                        <div
                          className={`h-full ${bar.color} rounded-[2px] transition-all duration-300`}
                          style={{ width: `${Math.max(2, widthPercent)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>

        {/* Cold-Start Curve Line Chart */}
        <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-[var(--color-text)] uppercase tracking-wider">
              Cold-Start Curve (History &rarr; Metric)
            </h4>
            <select
              aria-label="Select metric for cold-start curve"
              value={selectedCurveMetric}
              onChange={(e) => setSelectedCurveMetric(e.target.value as 'hit_rate@10' | 'ndcg@10' | 'recall@10')}
              className="h-7 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg)] px-2 text-xs text-[var(--color-text)] focus:outline-none"
            >
              <option value="hit_rate@10">Hit Rate @ 10</option>
              <option value="ndcg@10">nDCG @ 10</option>
              <option value="recall@10">Recall @ 10</option>
            </select>
          </div>

          {/* SVG Line Chart */}
          {(() => {
            const modCurve = coldStartCurves[modelName] || {};
            const popCurve = coldStartCurves['popularity'] || {};

            const points = historySteps.map((step) => ({
              step,
              modVal: Number(modCurve[step]?.[selectedCurveMetric]) || 0,
              popVal: Number(popCurve[step]?.[selectedCurveMetric]) || 0,
            }));

            const allVals = points.flatMap((p) => [p.modVal, p.popVal]);
            const maxVal = Math.max(...allVals, 0.001);

            const width = 280;
            const height = 110;
            const padX = 25;
            const padY = 15;

            const getX = (idx: number) => padX + (idx / (historySteps.length - 1)) * (width - 2 * padX);
            const getY = (val: number) => height - padY - (val / maxVal) * (height - 2 * padY);

            const modPath = points
              .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx)} ${getY(p.modVal)}`)
              .join(' ');

            const popPath = points
              .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx)} ${getY(p.popVal)}`)
              .join(' ');

            const chartDescription = points
              .map(
                (p) =>
                  `History size ${p.step}: ${modelName.toUpperCase()} = ${formatMetric(
                    p.modVal
                  )}, Popularity = ${formatMetric(p.popVal)}`
              )
              .join('; ');

            return (
              <div className="space-y-2">
                <svg
                  viewBox={`0 0 ${width} ${height}`}
                  className="w-full h-28 overflow-visible"
                  role="img"
                  aria-label={`Cold-start degradation curve (${selectedCurveMetric}): ${chartDescription}`}
                >
                  <desc>{chartDescription}</desc>
                  {/* Grid lines */}
                  <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="#2A2A2A" strokeWidth="1" />
                  <line x1={padX} y1={padY} x2={width - padX} y2={padY} stroke="#2A2A2A" strokeWidth="1" strokeDasharray="2,2" />

                  {/* Popularity Baseline Curve */}
                  <path d={popPath} fill="none" stroke="#71717A" strokeWidth="1.5" strokeDasharray="3,3" />

                  {/* Model Curve */}
                  <path d={modPath} fill="none" stroke="var(--color-accent)" strokeWidth="2" />

                  {/* Model Point Dots */}
                  {points.map((p, idx) => (
                    <circle
                      key={p.step}
                      cx={getX(idx)}
                      cy={getY(p.modVal)}
                      r="3"
                      className="fill-[var(--color-accent)]"
                      aria-label={`${modelName.toUpperCase()} history ${p.step}: ${formatMetric(p.modVal)}`}
                      data-history-step={p.step}
                      data-metric-value={formatMetric(p.modVal)}
                    >
                      <title>{`${modelName.toUpperCase()} history ${p.step}: ${formatMetric(p.modVal)}`}</title>
                    </circle>
                  ))}
                </svg>

                {/* Accessible text alternative table for screen readers and automated consistency audits */}
                <div className="sr-only" aria-label="Cold start curve data points">
                  <table>
                    <caption>Cold start curve points for {selectedCurveMetric}</caption>
                    <thead>
                      <tr>
                        <th>History</th>
                        <th>{modelName.toUpperCase()}</th>
                        <th>Popularity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {points.map((p) => (
                        <tr key={p.step} data-step={p.step}>
                          <td>{p.step}</td>
                          <td data-model-val>{formatMetric(p.modVal)}</td>
                          <td data-pop-val>{formatMetric(p.popVal)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* X-axis history size labels */}
                <div className="flex justify-between text-[12px] text-[var(--color-text-muted)] px-1">
                  {historySteps.map((s) => (
                    <span key={s} className="tabular-nums">
                      {s}h
                    </span>
                  ))}
                </div>

                <div className="flex items-center justify-center gap-4 text-[12px] pt-1 text-[var(--color-text-secondary)]">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[var(--color-accent)]" /> {modelName.toUpperCase()}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-zinc-500" /> Popularity Baseline
                  </span>
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* 6. Secondary Beyond-Accuracy Metrics Cards */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-3">
        <h4 className="text-xs font-bold text-[var(--color-text)] uppercase tracking-wider">
          Beyond-Accuracy Metrics @ {selectedK}
        </h4>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="rounded-[var(--radius-card)] bg-[var(--color-elevated)] p-3 border border-[var(--color-border)] space-y-1">
            <span className="text-[12px] text-[var(--color-text-muted)] block">Catalog Coverage</span>
            <span className="text-base font-bold text-[var(--color-text)] tabular-nums">
              {typeof currentModelData.coverage === 'number' ? `${(currentModelData.coverage * 100).toFixed(1)}%` : '—'}
            </span>
            <span className="text-[12px] text-[var(--color-text-secondary)] block">
              % items recommended to &ge;1 user
            </span>
          </div>

          <div className="rounded-[var(--radius-card)] bg-[var(--color-elevated)] p-3 border border-[var(--color-border)] space-y-1">
            <span className="text-[12px] text-[var(--color-text-muted)] block">Novelty</span>
            <span className="text-base font-bold text-[var(--color-text)] tabular-nums">
              {typeof currentModelData.novelty === 'number' ? `${currentModelData.novelty.toFixed(2)} bits` : '—'}
            </span>
            <span className="text-[12px] text-[var(--color-text-secondary)] block">
              Mean self-information (bits)
            </span>
          </div>

          <div className="rounded-[var(--radius-card)] bg-[var(--color-elevated)] p-3 border border-[var(--color-border)] space-y-1">
            <span className="text-[12px] text-[var(--color-text-muted)] block">Diversity</span>
            <span className="text-base font-bold text-[var(--color-text)] tabular-nums">
              {typeof currentModelData.diversity === 'number' ? formatMetric(currentModelData.diversity, 3) : '—'}
            </span>
            <span className="text-[12px] text-[var(--color-text-secondary)] block">
              Mean intra-list cosine distance
            </span>
          </div>

          <div className="rounded-[var(--radius-card)] bg-[var(--color-elevated)] p-3 border border-[var(--color-border)] space-y-1">
            <span className="text-[12px] text-[var(--color-text-muted)] block">Personalisation</span>
            <span className="text-base font-bold text-[var(--color-text)] tabular-nums">
              {typeof currentModelData.personalisation === 'number' ? `${(currentModelData.personalisation * 100).toFixed(1)}%` : '—'}
            </span>
            <span className="text-[12px] text-[var(--color-text-secondary)] block">
              Inter-user recommendation distance
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
