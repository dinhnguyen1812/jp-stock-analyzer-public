import { useState, useEffect } from "react";
import { Container, Spinner, Alert, Row, Col } from "react-bootstrap";
import { StockSearch } from "../components/longterm/StockSearch";
import { SummaryCard } from "../components/longterm/SummaryCard";
import { IndicatorsCard } from "../components/longterm/IndicatorsCard";
import { IndustryCard } from "../components/longterm/IndustryCard";
import { HistoricalChart } from "../components/longterm/HistoricalChart";
import { NewsCard } from "../components/longterm/NewsCard";
import { fetchStockAnalysis } from "../api";

function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    document.title = "Long term Stock Analyzer";
  }, []);

  const handleSearch = async (ticker: string) => {
    setLoading(true);
    setError("");
    setData(null);

    try {
      const result = await fetchStockAnalysis(ticker);

      // Handle possible JSON string in `summary`
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
      <Row>
        {/* Left Column: 1/3 width */}
        <Col md={4}>
          {data && (
            <SummaryCard
              summary={data.summary}
              sentiment={data.sentiment}
              epsOutlook={data.eps_outlook}
              expectedPrice={data.expected_price}
              reasoning={data.reasoning}
            />
          )}
        </Col>

        {/* Middle Column: 1/3 width */}
        <Col md={4}>
          <StockSearch onSearch={handleSearch} />
          {loading && <Spinner animation="border" />}
          {error && <Alert variant="danger">{error}</Alert>}
          {data && (
            <>
              <IndicatorsCard indicators={data.stock_data} />
              <IndustryCard industry={data.industry_data?.[0]} />
            </>
          )}
        </Col>

        {/* Right Column: 1/3 width */}
        <Col md={4}>
          {data && (
            <>
              <HistoricalChart data={data.historical} />
              <NewsCard height="350px" news={data.news} />
            </>
          )}
        </Col>
      </Row>
    </Container>
  );
}

export default App;
