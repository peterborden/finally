import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FinAlly',
  description: 'FinAlly — AI Trading Workstation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-base text-gray-200 font-mono antialiased">{children}</body>
    </html>
  );
}
