import { useState } from "react";
import { Container, Spinner, Alert } from "react-bootstrap";
import { StockSearch } from "./components/StockSearch";
import { SummaryCard } from "./components/SummaryCard";
import { IndicatorsCard } from "./components/IndicatorsCard";
import { IndustryCard } from "./components/IndustryCard";
import { HistoricalChart } from "./components/HistoricalChart";
import { NewsCard } from "./components/NewsCard";
import { fetchStockAnalysis } from "./api";

function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<any>(null);

  const handleSearch = async (ticker: string) => {
    setLoading(true);
    setError("");
    setData(null);

    try {
      const result = await fetchStockAnalysis(ticker);

      // Safety check: if summary is a stringified JSON, try to parse it
      let summaryData = result;
      if (typeof result.summary === "string" && result.summary.includes("{")) {
        try {
          const parsed = JSON.parse(result.summary);
          summaryData = {
            ...result,
            summary: parsed.summary,
            sentiment: parsed.sentiment || result.sentiment || "Unknown",
            eps_outlook: parsed.eps_outlook || result.eps_outlook || "N/A",
            reasoning: parsed.reasoning || "",
          };
        } catch (e) {
          console.warn("⚠️ Failed to parse GPT JSON summary:", e);
        }
      }

      setData(summaryData);
    } catch (err: any) {
      setError(err.message || "Failed to fetch analysis.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container className="py-4">
      <h2 className="mb-4">JP Stock Analyzer</h2>
      <StockSearch onSearch={handleSearch} />
      {loading && <Spinner animation="border" />}
      {error && <Alert variant="danger">{error}</Alert>}
      {data && (
        <>
          <SummaryCard
            summary={data.summary}
            sentiment={data.sentiment}
            epsOutlook={data.eps_outlook}
            reasoning={data.reasoning}
          />
          <IndicatorsCard indicators={data.stock_data} />
          <IndustryCard industry={data.industry_data?.[0]} />
          <HistoricalChart data={data.historical} />
          <NewsCard news={data.news} />
        </>
      )}
    </Container>
  );
}

export default App;
