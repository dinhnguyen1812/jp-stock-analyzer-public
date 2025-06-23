import { Card } from "react-bootstrap";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

interface HistoricalItem {
  date: string;
  per: number;
  pbr: number;
}

interface HistoricalChartProps {
  data: HistoricalItem[];
}

export const HistoricalChart: React.FC<HistoricalChartProps> = ({ data }) => {
  const chartData = data.map(d => ({
    date: d.date.slice(0, 10), // ensure format is "YYYY-MM-DD"
    per: d.per ?? null,
    pbr: d.pbr ?? null
  }));

  return (
    <Card className="mb-3">
      <Card.Header>📈 Historical PER & PBR</Card.Header>
      <Card.Body style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} angle={-45} textAnchor="end" />
            <YAxis yAxisId="left" label={{ value: 'PER', angle: -90, position: 'insideLeft' }} />
            <YAxis
              yAxisId="right"
              orientation="right"
              label={{ value: 'PBR', angle: 90, position: 'insideRight' }}
            />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="per" stroke="#8884d8" name="PER" yAxisId="left" />
            <Line type="monotone" dataKey="pbr" stroke="#82ca9d" name="PBR" yAxisId="right" />
          </LineChart>
        </ResponsiveContainer>
      </Card.Body>
    </Card>
  );
};
