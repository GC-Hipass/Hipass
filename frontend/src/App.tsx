import { Navigate, Route, Routes } from "react-router-dom";

import { DEMO_SEARCH, DEMO_SESSION_ID } from "./mocks/interviewDemo";
import InterviewPage from "./pages/InterviewPage";
import ResultPage from "./pages/ResultPage";
import SetupPage from "./pages/SetupPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SetupPage />} />
      <Route
        path="/mock/result"
        element={<Navigate to={`/result/${DEMO_SESSION_ID}${DEMO_SEARCH}`} replace />}
      />
      <Route path="/interview/:sessionId/:order" element={<InterviewPage />} />
      <Route path="/result/:sessionId" element={<ResultPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
