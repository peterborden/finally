/**
 * DOM CONTRACT — the single source of truth for the selectors the E2E suite
 * relies on. These `data-testid` values are REQUESTED from the Frontend engineer
 * (see planning/BUILD_LOG.md). Where a stable role/text selector is equally
 * robust, the helpers fall back to that so the suite degrades gracefully.
 *
 * Frontend engineer: please add these `data-testid` attributes. Grouped by §10 UI.
 */
export const testId = {
  // Header
  header: 'header',
  connectionStatus: 'connection-status', // has data-state="connected|reconnecting|disconnected"
  cashBalance: 'cash-balance',
  totalValue: 'portfolio-total-value',

  // Watchlist panel
  watchlist: 'watchlist',
  watchlistRow: (ticker: string) => `watchlist-row-${ticker.toUpperCase()}`,
  watchlistPrice: (ticker: string) => `watchlist-price-${ticker.toUpperCase()}`,
  watchlistChangePct: (ticker: string) => `watchlist-change-${ticker.toUpperCase()}`,
  watchlistSparkline: (ticker: string) => `sparkline-${ticker.toUpperCase()}`,
  addTickerInput: 'add-ticker-input',
  addTickerButton: 'add-ticker-button',
  removeTickerButton: (ticker: string) => `remove-ticker-${ticker.toUpperCase()}`,

  // Main chart
  mainChart: 'main-chart',
  mainChartTitle: 'main-chart-title',

  // Portfolio heatmap / treemap
  heatmap: 'portfolio-heatmap',
  heatmapTile: (ticker: string) => `heatmap-tile-${ticker.toUpperCase()}`,

  // P&L chart
  pnlChart: 'pnl-chart',

  // Positions table
  positionsTable: 'positions-table',
  positionRow: (ticker: string) => `position-row-${ticker.toUpperCase()}`,
  positionQty: (ticker: string) => `position-qty-${ticker.toUpperCase()}`,
  positionAvgCost: (ticker: string) => `position-avgcost-${ticker.toUpperCase()}`,
  positionPnl: (ticker: string) => `position-pnl-${ticker.toUpperCase()}`,

  // Trade bar
  tradeBar: 'trade-bar',
  tradeTickerInput: 'trade-ticker-input',
  tradeQtyInput: 'trade-qty-input',
  tradeBuyButton: 'trade-buy-button',
  tradeSellButton: 'trade-sell-button',

  // AI chat panel
  chatPanel: 'chat-panel',
  chatInput: 'chat-input',
  chatSend: 'chat-send-button',
  chatMessages: 'chat-messages',
  chatMessage: 'chat-message', // each message; role via data-role="user|assistant"
  chatLoading: 'chat-loading',
  chatActionBadge: 'chat-action', // inline trade/watchlist confirmation
} as const;

/** Default seed watchlist (PLAN §7). */
export const SEED_TICKERS = [
  'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
  'NVDA', 'META', 'JPM', 'V', 'NFLX',
] as const;

export const STARTING_CASH = 10000.0;
