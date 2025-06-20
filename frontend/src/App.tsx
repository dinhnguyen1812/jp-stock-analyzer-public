import { useState } from "react";
import { Container, Alert, Spinner } from "react-bootstrap";
import { StockSearch } from "./components/StockSearch";
import { StockCard } from "./components/StockCard";
import { NewsCard } from "./components/NewsCard";
import { fetchStock, fetchNews, type StockData, type NewsItem } from "./api";

function App() {
  const [stock, setStock] = useState<StockData | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async (ticker: string) => {
    setLoading(true);
    setError("");
    setStock(null);
    setNews([]);

    try {
      const stockData = await fetchStock(ticker);
      setStock(stockData);

      const newsData = await fetchNews(ticker);
      setNews(newsData);
    } catch (err) {
      setError((err as Error).message);
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
      {stock && <StockCard stock={stock} />}
      {news.length > 0 && <NewsCard news={news} />}
    </Container>
  );
}

export default App;
