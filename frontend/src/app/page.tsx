import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { HealthStatus } from '@/components/health-status';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1 className="text-2xl font-bold tracking-tight">ATLAS</h1>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <HealthStatus />
        </CardContent>
      </Card>
    </main>
  );
}
