import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ShortTermPage from "./pages/ShortTermPage";
import LongTermPage from "./pages/LongTermPage";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/shortterm" element={<ShortTermPage />} />
        <Route path="/longterm" element={<LongTermPage />} />
      </Routes>
    </Router>
  );
}

export default App;
