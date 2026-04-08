import { ClustersScreen } from '@/components/clusters/clusters-screen';
import { loadClustersScreenData } from '@/lib/api/clusters-shell';

export default async function ClustersPage() {
  const data = await loadClustersScreenData();
  return <ClustersScreen data={data} />;
}
