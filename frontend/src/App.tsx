import { Navigate, Route, Routes } from "react-router-dom";

import InterviewPage from "./pages/InterviewPage";
import ResultPage from "./pages/ResultPage";
import SetupPage from "./pages/SetupPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SetupPage />} />
      <Route path="/interview/:sessionId/:order" element={<InterviewPage />} />
      <Route path="/result/:sessionId" element={<ResultPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
