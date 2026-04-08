import { loadWatchlistScreenData } from '@/lib/api/watchlist-shell';
import { WatchlistScreen } from '@/components/watchlist/watchlist-screen';

export default async function WatchlistPage() {
  const data = await loadWatchlistScreenData();
  return <WatchlistScreen data={data} />;
}
