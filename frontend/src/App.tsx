import { Navigate, Route, Routes, useParams } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import NewSession from "./pages/NewSession";
import SessionDetail from "./pages/SessionDetail";

function LegacySessionRedirect() {
  const { sessionId } = useParams();
  return <Navigate to={`/sessions/${sessionId}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/projects" element={<Projects />} />
      <Route path="/sessions/new" element={<NewSession />} />
      <Route path="/sessions/:sessionId" element={<SessionDetail />} />
      {/* Backwards-compatible alias for the old URL scheme. */}
      <Route path="/session/:sessionId" element={<LegacySessionRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
