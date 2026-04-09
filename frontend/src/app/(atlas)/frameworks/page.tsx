import { FrameworksScreen } from '@/components/frameworks/frameworks-screen';
import { loadFrameworksScreenData } from '@/lib/api/frameworks';

export default async function FrameworksPage() {
  const frameworksScreenData = await loadFrameworksScreenData();

  return <FrameworksScreen data={frameworksScreenData} />;
}
