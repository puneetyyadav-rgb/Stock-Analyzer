import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const client = axios.create({ baseURL: API, timeout: 900000 });

export const searchStocks = (q) => client.get(`/search`, { params: { q } }).then((r) => r.data);
export const getOverview = (sym) => client.get(`/stock/${sym}/overview`).then((r) => r.data);
export const getChart = (sym, period = "1y") => client.get(`/stock/${sym}/chart`, { params: { period } }).then((r) => r.data);

export const getTechnicals = (sym) => client.get(`/stock/${sym}/technicals`).then((r) => r.data);
export const getFinancials = (sym) => client.get(`/stock/${sym}/financials`).then((r) => r.data);
export const getCorporate = (sym) => client.get(`/stock/${sym}/corporate`).then((r) => r.data);
export const getHolders = (sym) => client.get(`/stock/${sym}/holders`).then((r) => r.data);
export const getNews = (sym) => client.get(`/stock/${sym}/news`).then((r) => r.data);
export const getScreener = (sym) => client.get(`/stock/${sym}/screener`).then((r) => r.data);
export const getAIVerdict = (sym) => client.post(`/stock/${sym}/ai-verdict`).then((r) => r.data);
export const getAITechnical = (sym) => client.post(`/stock/${sym}/ai-technical`).then((r) => r.data);
export const getAINews = (sym) => client.post(`/stock/${sym}/ai-news`).then((r) => r.data);
export const getAIRatios = (sym, force = false, pdfData = null) => client.post(`/stock/${sym}/ai-ratios`, pdfData, { params: { force } }).then((r) => r.data);
export const getFactorLeaders = (n = 15, minAdvTurnoverCr = 5.0) => client.get(`/factors/leaders`, { params: { n, min_adv_turnover_cr: minAdvTurnoverCr } }).then((r) => r.data);
export const getFactorParamValidation = (params = {}) => client.get(`/factors/param-validation`, { params }).then((r) => r.data);
export const getMacro = () => client.get(`/macro`).then((r) => r.data);
export const getSectors = () => client.get(`/sectors`).then((r) => r.data);
export const getMarketDepth = (sym) => client.get(`/stock/${sym}/depth`).then((r) => r.data);
export const getMLPredict = (sym) => client.get(`/stock/${sym}/ml-predict`).then((r) => r.data);
export const getRegime = (sym) => client.get(`/stock/${sym}/regime`).then((r) => r.data);
export const getPatterns = (sym) => client.get(`/stock/${sym}/patterns`).then((r) => r.data);
export const getSocial = (sym) => client.get(`/stock/${sym}/social`).then((r) => r.data);
export const getNewsSplit = (sym) => client.get(`/stock/${sym}/news-split`).then((r) => r.data);
export const getSectorAnalysis = (sym) => client.get(`/stock/${sym}/sector-analysis`).then((r) => r.data);
export const getExternalScrape = (sym) => client.get(`/stock/${sym}/external-scrape`).then((r) => r.data);
export const getVerdictHistory = (sym) => client.get(`/stock/${sym}/verdict-history`).then((r) => r.data);
export const uploadSourceMaterial = (sym, file) => {
  const formData = new FormData();
  formData.append("file", file);
  return client.post(`/stock/${sym}/upload-source`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 600000
  }).then((r) => r.data);
};

export const getGlobalMacroMonteCarlo = async (params = {}, options = {}) => {
  try {
    const response = await client.get(`/macro/global-monte-carlo`, {
      params: {
        horizon_days: params.horizon_days ?? 20,
        paths: params.paths ?? 10000,
        lookback: params.lookback ?? 252,
        seed: params.seed ?? 12345,
        vol_scale: params.vol_scale ?? 1.0,
        regime_override: params.regime_override || "normal"
      },
      signal: options.signal,
      timeout: options.timeout ?? 900000
    });
    const data = response.data || {};
    if (!data.status) {
      data.status = "success";
    }
    return data;
  } catch (err) {
    if (axios.isCancel(err) || err.name === "AbortError") {
      return { status: "canceled", message: "Request was aborted by the user or timed out." };
    }
    return {
      status: "error",
      message: err.response?.data?.detail || err.message || "Failed to fetch global macro Monte Carlo simulation."
    };
  }
};

export const getBetaCoupledSimulation = async (sym, params = {}, options = {}) => {
  try {
    const response = await client.get(`/stock/${sym}/beta-coupled-simulation`, {
      params: {
        sector: params.sector || "Conglomerate",
        horizon_days: params.horizon_days ?? 20,
        paths: params.paths ?? 10000,
        lookback: params.lookback ?? 252,
        seed: params.seed ?? 12345,
        vol_scale: params.vol_scale ?? 1.0,
        regime_override: params.regime_override || "normal"
      },
      signal: options.signal,
      timeout: options.timeout ?? 900000
    });
    const data = response.data || {};
    if (!data.status) {
      data.status = "success";
    }
    return data;
  } catch (err) {
    if (axios.isCancel(err) || err.name === "AbortError") {
      return { status: "canceled", symbol: sym, message: "Request was aborted by the user or timed out." };
    }
    return {
      status: "error",
      symbol: sym,
      message: err.response?.data?.detail || err.message || "Failed to fetch stock beta-coupled simulation.",
      expected_stock_move: 0.0,
      downside_var: { var95: 0.0, var99: 0.0 },
      downside_cvar: 0.0,
      upside_beta: 1.0,
      downside_beta: 1.0,
      macro_factor_contribution: {},
      probability_of_loss: 0.0,
      probability_of_large_drawdown: 0.0
    };
  }
};

export const getCatalystsUpcoming = (days = 30) =>
  client.get(`/catalysts/upcoming`, { params: { days } }).then((r) => r.data);

export const runBatchArchive = (maxStocks = 2000, downloadPdfs = false, universeFilter = "all") =>
  client.post(`/catalysts/run-batch-archive`, null, { params: { max_stocks: maxStocks, download_pdfs: downloadPdfs, universe_filter: universeFilter } }).then((r) => r.data);

export const getScanProgress = () =>
  client.get(`/catalysts/scan-progress`).then((r) => r.data);

export const getResultsDue = (days = 30) =>
  client.get(`/catalysts/results-due`, { params: { days } }).then((r) => r.data);

