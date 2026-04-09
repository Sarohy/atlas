import { DailyBriefingScreen } from '@/components/daily-briefing/daily-briefing-screen';
import { loadDailyBriefingScreenData } from '@/lib/api/daily-briefing';

export default async function DailyBriefingPage() {
  const dailyBriefingScreenData = await loadDailyBriefingScreenData();

  return <DailyBriefingScreen data={dailyBriefingScreenData} />;
}
