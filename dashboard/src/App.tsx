import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import HistoryPage from './pages/HistoryPage';
import ImportPage from './pages/ImportPage';
import PlaysPage from './pages/PlaysPage';
import PositionsPage from './pages/PositionsPage';
import ScanPage from './pages/ScanPage';
import ScannerPage from './pages/ScannerPage';
import SettingsPage from './pages/SettingsPage';
import WatchlistsPage from './pages/WatchlistsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/scanner" element={<ScannerPage />} />
        <Route path="/watchlists" element={<WatchlistsPage />} />
        <Route path="/positions" element={<PositionsPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/plays" element={<PlaysPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/scanner" replace />} />
      </Route>
    </Routes>
  );
}
