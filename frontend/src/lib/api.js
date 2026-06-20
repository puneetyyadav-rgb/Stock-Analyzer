import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API, timeout: 60000 });

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
export const getMacro = () => client.get(`/macro`).then((r) => r.data);
export const getSectors = () => client.get(`/sectors`).then((r) => r.data);
export const getMarketDepth = (sym) => client.get(`/stock/${sym}/depth`).then((r) => r.data);
export const getMLPredict = (sym) => client.get(`/stock/${sym}/ml-predict`).then((r) => r.data);
export const getRegime = (sym) => client.get(`/stock/${sym}/regime`).then((r) => r.data);
export const getPatterns = (sym) => client.get(`/stock/${sym}/patterns`).then((r) => r.data);
