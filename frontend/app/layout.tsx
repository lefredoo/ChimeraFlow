import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ChimeraFlow - Data Correlation Engine",
  description: "Stitching Excel, Access, and WhatsApp into one correlated view for small businesses",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
