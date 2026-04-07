import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'ATLAS',
  description: 'Decision-support tool for active investing',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#0a0e1a] text-[#e8edf5]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
