import { PortfolioScreen } from '@/components/portfolio/portfolio-screen';
import { loadPortfolioScreenData } from '@/lib/api/portfolio';

export default async function PortfolioPage() {
  const portfolioScreenData = await loadPortfolioScreenData();

  return <PortfolioScreen data={portfolioScreenData} />;
}
